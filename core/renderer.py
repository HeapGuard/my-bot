import os
import base64
import mimetypes
import asyncio
from pathlib import Path
from urllib.parse import unquote, urlparse
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import config

class SlideRenderer:
    def __init__(self):
        self.templates_dir = config.TEMPLATES_DIR
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        self.template = self.env.get_template("slide.html")
        
        # Pre-load CSS content for inline embedding into HTML
        style_path = self.templates_dir / "style.css"
        with open(style_path, "r", encoding="utf-8") as f:
            self.css_content = f.read()

        # Threads logo — convert to base64 data URI for guaranteed rendering
        possible_paths = [
            config.BASE_DIR / "threads-logo.webp",
            config.BASE_DIR / "threads_logo.webp",
            self.templates_dir / "assets" / "threads_logo.webp",
            self.templates_dir / "assets" / "threads-logo.webp",
        ]
        self.threads_logo_url = ""
        for path in possible_paths:
            if path.exists():
                self.threads_logo_url = self._file_to_data_uri(path)
                break

    @staticmethod
    def _file_to_data_uri(file_path) -> str:
        """Reads a file and returns a base64 data URI string for inline HTML embedding."""
        file_path = Path(file_path)
        if not file_path.exists():
            return ""
        
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            # Common fallbacks
            suffix = file_path.suffix.lower()
            mime_map = {
                ".webp": "image/webp",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
            }
            mime_type = mime_map.get(suffix, "application/octet-stream")
        
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        
        return f"data:{mime_type};base64,{encoded}"

    def _resolve_image_url(self, url_or_path: str) -> str:
        """
        Converts a file path or file:// URI to a base64 data URI.
        If already a data URI or http(s) URL, returns as-is.
        """
        if not url_or_path:
            return ""
        
        # Already a data URI — pass through
        if url_or_path.startswith("data:"):
            return url_or_path
        
        # HTTP(S) URL — pass through (Playwright can fetch these)
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return url_or_path
        
        # file:// URI → extract local path
        if url_or_path.startswith("file:///"):
            parsed = urlparse(url_or_path)
            local_path = unquote(parsed.path)
            # On Windows, file:///C:/path → /C:/path, strip leading /
            if len(local_path) > 2 and local_path[0] == '/' and local_path[2] == ':':
                local_path = local_path[1:]
            return self._file_to_data_uri(local_path)
        
        # Assume it's a local filesystem path
        return self._file_to_data_uri(url_or_path)

    def render_html_for_slide(self, slide_data: dict, current_page: int, total_pages: int) -> str:
        """Renders HTML string for a given slide dictionary."""
        return self.template.render(
            slide=slide_data,
            current_page=current_page,
            total_pages=total_pages,
            brand_handle=config.BRAND_HANDLE,
            threads_logo_url=self.threads_logo_url,
            css_content=self.css_content
        )

    async def render_slides_to_images(self, slides: list[dict], output_dir: Path) -> list[Path]:
        """
        Renders a list of slide dictionaries to 1080x1350 PNG files using Playwright.
        Returns paths to generated PNG images.
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        total_pages = len(slides)
        generated_paths = []

        async with async_playwright() as p:
            # Launch Chrome with VPS friendly flags
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context(
                viewport={"width": 1080, "height": 1350},
                device_scale_factor=1
            )
            page = await context.new_page()

            for i, slide in enumerate(slides, start=1):
                # Convert any file paths / file:// URIs to base64 data URIs before rendering
                if slide.get("image_url"):
                    slide["image_url"] = self._resolve_image_url(slide["image_url"])
                
                html_content = self.render_html_for_slide(slide, current_page=i, total_pages=total_pages)
                
                # Set content and wait for network (fonts & images) to be loaded
                await page.set_content(html_content, wait_until="networkidle")
                
                output_file = output_dir / f"slide_{i:02d}.png"
                await page.screenshot(
                    path=str(output_file),
                    type="png",
                    full_page=False
                )
                generated_paths.append(output_file)

            await browser.close()

        return generated_paths
