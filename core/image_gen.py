import os
import asyncio
import urllib.parse
import httpx
from pathlib import Path
import config

class ImageGenerator:
    def __init__(self):
        self.proxy = config.HTTP_PROXY if config.HTTP_PROXY else None

    async def generate_image(self, prompt: str, output_path: Path) -> str:
        """
        Generates an atmospheric image from a prompt and saves it locally.
        Primary: Pollinations.ai FLUX model.
        Fallback: Unsplash Dark Ambient visual source.
        Returns file URI string if successful.
        """
        output_path.parent.mkdir(exist_ok=True, parents=True)

        enhanced_prompt = (
            f"{prompt}, dark moody aesthetic, cinematic lighting, 8k resolution, "
            f"dramatic fog, dark charcoal tones, realistic photography"
        )
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        url_pollinations = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=1000&nologo=true&seed=42"

        async with httpx.AsyncClient(timeout=30.0, proxy=self.proxy) as client:
            for attempt in range(2):
                try:
                    response = await client.get(url_pollinations)
                    if response.status_code == 200 and len(response.content) > 5000:
                        with open(output_path, "wb") as f:
                            f.write(response.content)
                        return str(output_path.resolve())
                    elif response.status_code == 429:
                        print(f"[ImageGen] Pollinations 429 rate limit reached, waiting 2s...")
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f"[ImageGen] Pollinations attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(1)

            # Fallback to high quality atmospheric dark image search matching the topic
            words = [w.strip(",.()\"'").lower() for w in prompt.split() if len(w) > 3]
            keywords = ",".join(words[:4]) if words else "dark,mystery"
            fallback_url = f"https://images.unsplash.com/featured/800x1000/?{urllib.parse.quote(keywords)}"
            
            print(f"[ImageGen] Falling back to Unsplash query: {keywords}")
            try:
                fb_res = await client.get(fallback_url, follow_redirects=True)
                if fb_res.status_code == 200 and len(fb_res.content) > 5000:
                    with open(output_path, "wb") as f:
                        f.write(fb_res.content)
                    return str(output_path.resolve())
            except Exception as fb_err:
                print(f"[ImageGen] Fallback image download failed: {fb_err}")

        return ""

    async def close(self):
        pass
