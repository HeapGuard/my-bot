import os
import sys
import asyncio
import re

import logging
import zipfile
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.client.session.aiohttp import AiohttpSession

import config
from core.llm import StoryEngine
from core.image_gen import ImageGenerator
from core.renderer import SlideRenderer
from db.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from aiogram.client.telegram import TelegramAPIServer
import aiohttp
from aiohttp.resolver import AbstractResolver

class CustomDNSResolver(AbstractResolver):
    def __init__(self):
        self._resolver = aiohttp.resolver.ThreadedResolver()
        
    async def resolve(self, host, port=0, family=0):
        # Direct DNS Pinning to official Telegram Bot API IP (bypasses ISP DNS blocks)
        if host == "api.telegram.org":
            return [{
                "hostname": "api.telegram.org",
                "host": "149.154.166.110",
                "port": port,
                "family": family,
                "proto": 0,
                "flags": 0
            }]
        return await self._resolver.resolve(host, port, family)

    async def close(self):
        await self._resolver.close()

class CustomAiohttpSession(AiohttpSession):
    async def create_session(self) -> aiohttp.ClientSession:
        connector = aiohttp.TCPConnector(resolver=CustomDNSResolver(), ssl=False)
        return aiohttp.ClientSession(
            connector=connector,
            connector_owner=True
        )

bot = None

dp = Dispatcher()
db = Database()

llm = StoryEngine()
renderer = SlideRenderer()

# Message buffer for combining multi-part messages from Telegram's 4096 char limit
pending_messages: dict[int, dict] = {}  # user_id -> {"texts": [...], "task": asyncio.Task, "message": Message}

def escape_md_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2 parse mode."""
    # Characters that need escaping in MarkdownV2
    special_chars = r'_[]()~`>#+-=|{}.!'
    result = ""
    i = 0
    while i < len(text):
        # Preserve **bold** markers — convert to MarkdownV2 bold
        if text[i:i+2] == '**':
            result += '*'
            i += 2
            continue
        # Preserve _italic_ markers
        if text[i] == '_' and i > 0 and text[i-1] != '\\':
            # Check if this is part of _italic_ pair — let it through
            result += '_'
            i += 1
            continue
        if text[i] in special_chars:
            result += '\\' + text[i]
        else:
            result += text[i]
        i += 1
    return result


def format_channel_post(story_data: dict) -> str:
    """
    Formats a beautiful Markdown post from story data, ready for Telegram/Threads channel.
    Uses MarkdownV2 compatible formatting.
    """
    channel_text = story_data.get("channel_text", "")
    
    if channel_text:
        return channel_text
    
    # Fallback: build from slides
    title = story_data.get("title", "История")
    slides = story_data.get("slides", [])
    
    parts = [f"📖 **{title}**\n"]
    
    for slide in slides:
        stype = slide.get("type", "")
        text = slide.get("text", "").strip()
        
        if stype == "story" and text:
            clean = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
            clean = clean.replace("\\n\\n", "\n\n").replace("\\n", "\n")
            parts.append(clean)
        elif stype == "accent" and text:
            clean = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
            parts.append(clean)
        elif stype == "ending":
            if text:
                clean = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
                parts.append(f"✦ {clean}")
            question = slide.get("question", "")
            if question:
                parts.append(f"\n💬 _{question}_")
    
    parts.append("\n📌 **Подписывайся, чтобы не пропустить новые истории!**")
    
    return "\n\n".join(parts)


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = (
        f"👋 **Привет! Я бот {config.BRAND_NAME}.**\n\n"
        f"Я превращаю любые истории, темы или статьи в вирусные карусели слайдов (1080×1350) "
        f"для Threads, Instagram и Telegram Stories.\n\n"
        f"📌 **Как пользоваться:**\n"
        f"Просто отправь мне текст истории или тему, например:\n"
        f"└ *\"История про человека, который нашёл на чердаке старую шкатулку\"*\n\n"
        f"✨ **Что я сделаю:**\n"
        f"1. Напишу захватывающий сценарий с клиффхэнгерами\n"
        f"2. Создам атмосферные иллюстрации\n"
        f"3. Оформлю готовые стильные карточки с водяным знаком `{config.BRAND_HANDLE}`\n\n"
        f"💡 *Если текст большой — можешь отправить несколькими сообщениями, я подожду 3 секунды и объединю их.*"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: types.Message):
    """
    Buffers incoming text messages for 3 seconds to handle Telegram's 4096 char split.
    After the buffer timeout, combines all messages and starts generation.
    """
    user_id = message.from_user.id
    
    if user_id in pending_messages:
        # Add to existing buffer
        pending_messages[user_id]["texts"].append(message.text.strip())
        pending_messages[user_id]["message"] = message
        # Cancel the old timer — restart the 3s window
        pending_messages[user_id]["task"].cancel()
    else:
        # Start new buffer
        pending_messages[user_id] = {
            "texts": [message.text.strip()],
            "message": message
        }
    
    # Set a 3-second timer to process the buffer
    task = asyncio.create_task(_process_after_delay(user_id))
    pending_messages[user_id]["task"] = task


async def _process_after_delay(user_id: int):
    """Waits 3 seconds then processes all buffered messages for a user."""
    try:
        await asyncio.sleep(3)
    except asyncio.CancelledError:
        # Timer was cancelled because more messages arrived — don't process yet
        return
    
    # Grab and clear the buffer
    if user_id not in pending_messages:
        return
    
    buffer = pending_messages.pop(user_id)
    combined_text = "\n\n".join(buffer["texts"])
    message = buffer["message"]
    
    await _handle_story_generation(message, combined_text)


async def _handle_story_generation(message: types.Message, user_prompt: str):
    """Core story generation logic — processes combined user text."""
    parts_count = user_prompt.count("\n\n") + 1
    if parts_count > 1:
        status_msg = await message.answer(
            f"📝 **Получено {parts_count} частей текста, объединяю...**\n"
            f"⌛ **Генерирую сценарий карусели и оформляю карточки...**\n*Это займет 10–20 секунд.*",
            parse_mode="Markdown"
        )
    else:
        status_msg = await message.answer(
            "⌛ **Генерирую сценарий карусели и оформляю карточки...**\n*Это займет 10–20 секунд.*",
            parse_mode="Markdown"
        )

    try:
        # 1. Generate text story JSON
        story_data = await llm.generate_carousel_story(user_prompt)
        slides = story_data.get("slides", [])

        if not slides:
            await status_msg.edit_text("❌ Не удалось сгенерировать историю. Попробуйте сформулировать иначе.")
            return

        # Save to DB
        story_id = db.save_story(message.from_user.id, story_data.get("title", ""), user_prompt, slides)

        # 2. Generate images
        img_gen = ImageGenerator()
        output_dir = config.OUTPUT_DIR / f"story_{story_id}_{int(time.time())}"
        images_dir = output_dir / "images"

        for idx, slide in enumerate(slides, start=1):
            image_prompt = slide.get("image_prompt")
            if image_prompt and slide.get("type") in ["cover", "accent", "outro"]:
                img_path = images_dir / f"img_{idx:02d}.jpg"
                file_path = await img_gen.generate_image(image_prompt, img_path)
                if file_path:
                    slide["image_url"] = file_path

        await img_gen.close()

        # 3. Render Playwright PNG slides
        png_paths = await renderer.render_slides_to_images(slides, output_dir)

        # 4. Prepare Telegram Media Group
        media_group = []
        for i, path in enumerate(png_paths):
            caption = f"📖 {story_data.get('title')}" if i == 0 else None
            media_group.append(InputMediaPhoto(media=FSInputFile(str(path)), caption=caption))

        # Send Media Group (carousel)
        await status_msg.delete()
        await message.answer_media_group(media=media_group)

        # 5. Send formatted channel post as a separate message
        channel_post = format_channel_post(story_data)
        if channel_post:
            try:
                await message.answer(
                    f"📋 **Готовый текст для канала:**\n\n{channel_post}",
                    parse_mode="Markdown"
                )
            except Exception as fmt_err:
                # If Markdown fails, send as plain text
                logging.warning(f"Markdown formatting failed, sending plain: {fmt_err}")
                await message.answer(
                    f"📋 Готовый текст для канала:\n\n{channel_post}"
                )

        # Send Action Keyboard
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 Скачать ZIP-архив", callback_data=f"zip_{story_id}"),
                InlineKeyboardButton(text="🔄 Перегенерировать", callback_data=f"regen_{story_id}")
            ]
        ])
        await message.answer(f"✅ **Карусель из {len(png_paths)} слайдов готова!**", reply_markup=kb, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Error handling story generation: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ произошла ошибка при генерации: {e}")

@dp.callback_query(F.data.startswith("zip_"))
async def handle_zip_download(callback: types.CallbackQuery):
    story_id = int(callback.data.split("_")[1])
    story = db.get_story(story_id)
    if not story:
        await callback.answer("История не найдена.", show_alert=True)
        return

    await callback.answer("Формирую ZIP-архив...")
    
    # Find matching output directory or render again if needed
    matching_dirs = list(config.OUTPUT_DIR.glob(f"story_{story_id}_*"))
    if not matching_dirs:
        await callback.message.answer("Файлы устарели. Сгенерируйте заново.")
        return

    target_dir = matching_dirs[-1]
    png_files = sorted(target_dir.glob("slide_*.png"))

    zip_path = target_dir / f"carousel_story_{story_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in png_files:
            zipf.write(file, arcname=file.name)

    await callback.message.answer_document(
        document=FSInputFile(str(zip_path)),
        caption=f"📦 **Архив слайдов для публикации**\nЗаголовок: *{story.get('title')}*",
        parse_mode="Markdown"
    )

async def main():
    global bot
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("[BOT WARNING] BOT_TOKEN is not set in .env!")
        print("Please set BOT_TOKEN in .env to run Telegram Bot.")
        print("You can still test image rendering locally by running: python test_render.py")
        return

    # Initialize Bot with CustomAiohttpSession inside the running event loop context
    api_server = TelegramAPIServer.from_base(config.TELEGRAM_API_URL)
    session = CustomAiohttpSession(api=api_server)
    bot = Bot(token=config.BOT_TOKEN, session=session)

    print(f"Launching StoriesHub Bot for handle {config.BRAND_HANDLE}...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
