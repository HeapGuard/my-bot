import json
import re
import httpx
import config

STORY_PROMPT_TEMPLATE = """
Ты — главный сценарист и эксперт по вирусным каруселям в Threads, Instagram и Telegram.
Твоя задача — взять входную историю или тему, полностью переписать её (сократить, но сохранить ВСЕ ключевые детали, имена, факты и развязку) и разбить на 8-10 карточек-слайдов.

КРИТИЧЕСКИ ВАЖНО — ПОЛНОТА ИСТОРИИ:
1. САМОЕ ГЛАВНОЕ: История должна быть рассказана ПОЛНОСТЬЮ от начала до конца. Нельзя обрывать на середине!
2. Каждый сюжетный поворот, каждая деталь должна быть раскрыта. Читатель должен понять ВСЮ историю.
3. Используй 6-8 слайдов типа "story" чтобы хватило места на всю историю.

ТРЕБОВАНИЯ К ФОРМАТУ И ДЛИНЕ ТЕКСТА:
1. ОГРАНИЧЕНИЕ ПО ДЛИНЕ: На одном слайде максимум 60-80 слов (до 450 символов с пробелами). 
2. ПОСЛЕДОВАТЕЛЬНОСТЬ СЮЖЕТА: История развивается последовательно. Каждый слайд "story" — одна сцена или мысль, плавно переходящая в следующую.
3. КЛИФФХЭНГЕРЫ: Заканчивай каждый текстовый слайд интригующей фразой, заставляющей листать дальше.
4. Выделение жирным: Выделяй ключевые драматические слова через HTML-теги `<b>важные слова</b>` (не более 1-2 выделений на слайд).
5. Разделение абзацев: Разделяй текст на слайде на короткие абзацы по 1-2 предложения с двойным переносом `\\n\\n`.
6. ТИПЫ СЛАЙДОВ:
   - "cover": Заголовок обложки — это КЛИКБЕЙТНАЯ ИНТРИГА, конкретная суть истории (6-10 слов, НЕ абстрактная фраза!). image_prompt для обложки.
   - "story": Сюжетный текстовый слайд (до 70 слов). Используй 6-8 таких слайдов.
   - "accent": Слайд с иллюстрацией посередине и коротким текстом снизу (до 40 слов), обязательно укажи image_prompt. Используй 1-2 таких слайда в ключевых моментах.
   - "ending": Мораль или вывод конкретно ЭТОЙ истории (до 40 слов) + вопрос к аудитории по теме ЭТОЙ истории в поле "question" (до 15 слов).
   - "outro": Призыв подписаться ("ПОДПИСЫВАЙСЯ, ЧТОБЫ НЕ ПРОПУСТИТЬ НОВЫЕ ИСТОРИИ"), image_prompt для фона.

7. ЗАГОЛОВОК title: Это полное название истории для канала (15-25 слов), раскрывающее суть и интригу. Не обрезай!

8. ТЕКСТ ДЛЯ КАНАЛА channel_text: Напиши полный текст истории в Markdown формате для публикации в Telegram/Threads канале. Используй:
   - **жирный** для ключевых слов
   - Абзацы через пустую строку
   - Эмодзи в начале абзацев для визуального оформления
   - В конце — вопрос к аудитории и призыв подписаться
   - Объём: 800-1500 символов

ВАЖНО: НЕ используй слайды типа "quote" — они не нужны. Используй только cover, story, accent, ending, outro.

Формат ответа MUST BE strictly a valid JSON object matching this exact schema:

{
  "title": "ПОЛНЫЙ ЗАГОЛОВОК ИСТОРИИ — КОНКРЕТНАЯ ИНТРИГА (15-25 слов)",
  "channel_text": "Полный markdown текст истории для публикации в канале...",
  "slides": [
    {
      "type": "cover",
      "title": "КЛИКБЕЙТ ЗАГОЛОВОК — СУТЬ ИНТРИГИ",
      "text": "",
      "image_prompt": "English image generation prompt describing a dark cover scene matching the theme"
    },
    {
      "type": "story",
      "text": "Начало истории... <b>первая деталь</b>...",
      "image_prompt": ""
    },
    {
      "type": "story",
      "text": "Продолжение... <b>неожиданный поворот</b>...",
      "image_prompt": ""
    },
    {
      "type": "story",
      "text": "Развитие сюжета...",
      "image_prompt": ""
    },
    {
      "type": "accent",
      "text": "Кульминационный момент...",
      "image_prompt": "English prompt for accent image scene"
    },
    {
      "type": "story",
      "text": "Продолжение после кульминации...",
      "image_prompt": ""
    },
    {
      "type": "story",
      "text": "Ещё одна деталь развязки...",
      "image_prompt": ""
    },
    {
      "type": "story",
      "text": "Финальные события...",
      "image_prompt": ""
    },
    {
      "type": "ending",
      "text": "Мораль или вывод конкретно этой истории.",
      "question": "Вопрос по теме этой конкретной истории?",
      "image_prompt": ""
    },
    {
      "type": "outro",
      "text": "ПОДПИСЫВАЙСЯ, ЧТОБЫ НЕ ПРОПУСТИТЬ НОВЫЕ ИСТОРИИ",
      "image_prompt": "Dark mysterious keyhole with subtle light beam, dark matte minimal aesthetic"
    }
  ]
}

Входная история / тема:
\"\"\"
{user_input}
\"\"\"
"""

class StoryEngine:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY

    async def generate_carousel_story(self, user_input: str) -> dict:
        """
        Sends user input to Gemini API and returns structured carousel slides dictionary.
        Safe against format key errors and network connection timeouts.
        """
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY":
            return self._get_demo_story(user_input)

        prompt = STORY_PROMPT_TEMPLATE.replace("{user_input}", user_input)
        models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
        
        timeout = httpx.Timeout(30.0, connect=10.0)
        proxy = config.HTTP_PROXY if config.HTTP_PROXY else None
        async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "responseMimeType": "application/json"
                    }
                }

                try:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        result = self._clean_and_parse_json(raw_text)
                        # Ensure channel_text exists
                        if "channel_text" not in result:
                            result["channel_text"] = self._build_channel_text(result)
                        return result
                    else:
                        print(f"[LLM] Notice: {model_name} status ({response.status_code}): {response.text}")
                except Exception as e:
                    print(f"[LLM] Network exception calling {model_name}: {e}")

        print("[LLM] Returning fallback story scenario due to API network timeout or key limit.")
        return self._get_demo_story(user_input)

    def _clean_and_parse_json(self, raw_text: str) -> dict:
        """Cleans markdown codeblocks and parses JSON."""
        cleaned = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    def _build_channel_text(self, story_data: dict) -> str:
        """
        Builds a formatted Markdown channel post from story_data when LLM doesn't provide one.
        """
        title = story_data.get("title", "История")
        slides = story_data.get("slides", [])
        
        parts = [f"📖 **{title}**\n"]
        
        for slide in slides:
            stype = slide.get("type", "")
            text = slide.get("text", "").strip()
            
            if stype == "story" and text:
                # Clean HTML bold tags → Markdown bold
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

    def _get_demo_story(self, user_input: str) -> dict:
        """
        Fallback logic: Intelligently splits the user's input text into engaging story cards
        if the Gemini API fails or is unavailable. This ensures the user's actual text is used.
        """
        # Split text into sentences (more granular than paragraphs)
        raw_parts = re.split(r'(?<=[.!?])\s+|\n+', user_input)
        sentences = [s.strip() for s in raw_parts if len(s.strip()) > 5]
        
        if len(sentences) < 3:
            # Input too short — use as-is with padding
            sentences = [user_input]

        # Build a meaningful title from the input (up to 60 chars)
        first_line = user_input.split('\n')[0].strip()
        if len(first_line) > 60:
            # Cut at last word boundary within 60 chars
            topic_title = first_line[:60].rsplit(' ', 1)[0].upper() + "..."
        else:
            topic_title = first_line.upper() if first_line else "НЕВЕРОЯТНАЯ ИСТОРИЯ"
        
        if not topic_title or len(topic_title) < 5:
            topic_title = "НЕВЕРОЯТНАЯ ИСТОРИЯ"

        # Group sentences into 6-7 slide chunks for a complete story
        total_sentences = len(sentences)
        target_slides = min(max(total_sentences // 2, 3), 7)  # 3-7 story slides
        
        # Distribute sentences evenly across slides
        slide_texts = []
        chunk_size = max(1, total_sentences // target_slides)
        
        for i in range(0, total_sentences, chunk_size):
            chunk = sentences[i:i + chunk_size]
            combined = " ".join(chunk)
            # Limit each slide to 500 chars
            if len(combined) > 500:
                combined = combined[:497] + "..."
            slide_texts.append(combined)
        
        # Ensure we don't have too many slides
        if len(slide_texts) > 7:
            # Merge the last ones
            merged = " ".join(slide_texts[6:])
            slide_texts = slide_texts[:6] + [merged[:500]]

        # Build slides
        slides = []
        
        # 1. Cover
        slides.append({
            "type": "cover",
            "title": topic_title,
            "text": "",
            "image_prompt": f"Dramatic dark mysterious visual related to {topic_title.lower()}"
        })

        # 2. Story slides with accent in the middle
        accent_idx = len(slide_texts) // 2  # Place accent in the middle
        
        for i, text in enumerate(slide_texts):
            # Add <b> to first important phrase in each slide
            words = text.split()
            if len(words) > 4:
                bold_phrase = " ".join(words[:3])
                text_with_bold = f"<b>{bold_phrase}</b> " + " ".join(words[3:])
            else:
                text_with_bold = text
            
            if i == accent_idx:
                slides.append({
                    "type": "accent",
                    "text": text_with_bold,
                    "image_prompt": f"Moody atmospheric scene, dark charcoal tones, dramatic lighting"
                })
            else:
                slides.append({
                    "type": "story",
                    "text": text_with_bold,
                    "image_prompt": ""
                })

        # 3. Ending — use last sentence as moral/conclusion
        last_text = sentences[-1] if sentences else "Каждое маленькое решение ведет к большим открытиям."
        ending_text = last_text if len(last_text) < 200 else last_text[:197] + "..."
        
        slides.append({
            "type": "ending",
            "text": ending_text,
            "question": "Что бы вы сделали на его месте?",
            "image_prompt": ""
        })

        # 4. Outro
        slides.append({
            "type": "outro",
            "text": "ПОДПИСЫВАЙСЯ, ЧТОБЫ НЕ ПРОПУСТИТЬ НОВЫЕ ИСТОРИИ",
            "image_prompt": "Dark mysterious keyhole with subtle light beam, dark matte minimal aesthetic"
        })

        # Build channel text from the story
        channel_text_parts = [f"📖 **{topic_title}**\n"]
        for text in slide_texts:
            clean = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
            channel_text_parts.append(clean)
        channel_text_parts.append(f"\n✦ {ending_text}")
        channel_text_parts.append("\n📌 **Подписывайся, чтобы не пропустить новые истории!**")

        return {
            "title": topic_title,
            "channel_text": "\n\n".join(channel_text_parts),
            "slides": slides
        }
