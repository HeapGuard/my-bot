import asyncio
import sys
import time
from pathlib import Path

import config
from core.llm import StoryEngine
from core.image_gen import ImageGenerator
from core.renderer import SlideRenderer

async def run_test():
    print("=== StoriesHub Local Test Render ===")
    start_time = time.time()

    # 1. Initialize components
    llm = StoryEngine()
    img_gen = ImageGenerator()
    renderer = SlideRenderer()

    # 2. Topic/Story prompt
    prompt = "История про то, как парень нашёл старый ключ возле подъезда и открыл заброшенную дверь в подвале"
    print(f"[1/4] Generating story script with AI for topic: '{prompt}'...")
    
    story_data = await llm.generate_carousel_story(prompt)
    print(f" -> Story generated: '{story_data.get('title')}' with {len(story_data.get('slides', []))} slides.")

    # 3. Generate visual backgrounds for cover & accent slides
    output_dir = config.OUTPUT_DIR / f"carousel_{int(time.time())}"
    images_dir = output_dir / "images"
    
    print("[2/4] Generating dark atmospheric visual images...")
    slides = story_data.get("slides", [])
    for idx, slide in enumerate(slides, start=1):
        image_prompt = slide.get("image_prompt")
        if image_prompt and slide.get("type") in ["cover", "accent", "outro"]:
            print(f" -> Generating image for Slide {idx} ({slide['type']}): '{image_prompt[:40]}...'")
            img_path = images_dir / f"img_{idx:02d}.jpg"
            file_uri = await img_gen.generate_image(image_prompt, img_path)
            if file_uri:
                slide["image_url"] = file_uri

    await img_gen.close()

    # 4. Render HTML/CSS to 1080x1350 PNGs
    print("[3/4] Rendering 1080x1350 PNG slide cards with Playwright...")
    png_paths = await renderer.render_slides_to_images(slides, output_dir)

    elapsed = time.time() - start_time
    print(f"[4/4] DONE in {elapsed:.2f}s! Generated {len(png_paths)} images in:")
    print(f"      {output_dir.resolve()}")
    for path in png_paths:
        print(f"  - {path.name} ({path.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    asyncio.run(run_test())
