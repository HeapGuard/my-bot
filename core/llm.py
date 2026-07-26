import json
import re
import httpx
import config

CHANNEL_CTA = "[Интересные стори. Подписаться](https://t.me/+qf7-zKuy2S5hYmYy)"

STORY_PROMPT_TEMPLATE = """
Ты — талантливый сценарист вирусных каруселей для Threads, Instagram и Telegram.

ТВОЯ ГЛАВНАЯ ЗАДАЧА:
Взять входную историю (которая может быть плохо написана, сумбурна или скучна) и ПОЛНОСТЬЮ ПЕРЕПИСАТЬ её:
- Сделай текст живым, цепляющим, интригующим — как будто рассказывает харизматичный рассказчик
- Упрости сложные предложения, убери канцеляризмы
- Добавь драматургию: завязка → нарастание → кульминация → развязка
- Сохрани ВСЕ ключевые факты, имена и детали, но подай их ярко
- Каждый слайд должен заканчиваться так, чтобы читатель ХОТЕЛ листать дальше

СТРОГИЕ ОГРАНИЧЕНИЯ:
1. МАКСИМУМ 6-8 СЛАЙДОВ ВСЕГО (включая cover, ending, outro). НЕ БОЛЬШЕ 8!
2. НА ОДНОМ СЛАЙДЕ МАКСИМУМ 35-45 СЛОВ (до 280 символов). Это ЖЁСТКИЙ лимит! Если текст длиннее — он будет ОБРЕЗАН на экране!
3. Текст на слайде: 2-3 коротких предложения максимум. Разделяй абзацы через `\\n\\n`.
4. История должна быть рассказана ПОЛНОСТЬЮ от начала до конца за 4-6 story-слайдов.

ПРАВИЛА ВЫДЕЛЕНИЯ ЖИРНЫМ:
- Выделяй через `<b>...</b>` ТОЛЬКО эмоционально заряженные слова/фразы: развязки, шокирующие факты, ключевые повороты
- НЕ выделяй первые слова предложения, обычные глаголы, предлоги, местоимения
- Максимум 1 выделение на слайд, 2-4 слова в выделении
- Примеры ХОРОШИХ выделений: `<b>отказался платить</b>`, `<b>оказался мошенником</b>`, `<b>потерял всё</b>`
- Примеры ПЛОХИХ выделений: `<b>Он пришёл</b>`, `<b>Я в</b>`, `<b>общих чертах</b>`

ТИПЫ СЛАЙДОВ:
- "cover": Кликбейтный заголовок — суть интриги в 6-10 словах. + image_prompt
- "story": Сюжетный слайд (СТРОГО до 40 слов). 4-5 таких слайдов.
- "accent": Слайд с картинкой + короткий текст (до 25 слов). Один в кульминации. + image_prompt
- "ending": Мораль/вывод ЭТОЙ истории (до 30 слов) + вопрос аудитории в "question" (до 12 слов)
- "outro": Призыв "ПОДПИСЫВАЙСЯ, ЧТОБЫ НЕ ПРОПУСТИТЬ НОВЫЕ ИСТОРИИ" + image_prompt

НЕ используй тип "quote"! Только: cover, story, accent, ending, outro.

ТЕКСТ ДЛЯ КАНАЛА (поле channel_text):
Напиши красивый пост для Telegram-канала в Markdown формате:
- Начни с заголовка: `# Заголовок истории`
- Разбей на абзацы подзаголовками `## Подзаголовок` где уместно
- Используй **жирный** для ключевых фраз
- Используй _курсив_ для мыслей/цитат
- Используй эмодзи для оформления
- Используй > для цитат или выводов
- В конце ОБЯЗАТЕЛЬНО поставь: `[Интересные стори. Подписаться](https://t.me/+qf7-zKuy2S5hYmYy)`
- Объём: 600-1200 символов

Формат ответа — СТРОГО валидный JSON:

{
  "title": "ПОЛНЫЙ ЗАГОЛОВОК — КОНКРЕТНАЯ ИНТРИГА",
  "channel_text": "# Заголовок\\n\\nТекст поста в markdown формате...\\n\\n[Интересные стори. Подписаться](https://t.me/+qf7-zKuy2S5hYmYy)",
  "slides": [
    {
      "type": "cover",
      "title": "КЛИКБЕЙТ — СУТЬ ИНТРИГИ",
      "text": "",
      "image_prompt": "English dark cinematic image prompt"
    },
    {
      "type": "story",
      "text": "Короткий текст до 40 слов...",
      "image_prompt": ""
    },
    {
      "type": "accent",
      "text": "Кульминация до 25 слов...",
      "image_prompt": "English prompt for accent scene"
    },
    {
      "type": "ending",
      "text": "Вывод до 30 слов.",
      "question": "Вопрос до 12 слов?",
      "image_prompt": ""
    },
    {
      "type": "outro",
      "text": "ПОДПИСЫВАЙСЯ, ЧТОБЫ НЕ ПРОПУСТИТЬ НОВЫЕ ИСТОРИИ",
      "image_prompt": "Dark mysterious keyhole, dark matte minimal aesthetic"
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
                        # Ensure channel_text exists and has correct CTA
                        if "channel_text" not in result:
                            result["channel_text"] = self._build_channel_text(result)
                        else:
                            # Ensure CTA link is correct
                            result["channel_text"] = self._fix_channel_cta(result["channel_text"])
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

    @staticmethod
    def _fix_channel_cta(text: str) -> str:
        """Ensures the channel text ends with the correct CTA link."""
        # Remove any existing generic CTA
        text = re.sub(
            r'(📌\s*\*?\*?)?Подписывайся.*?новые истории.*?(\*?\*?)?\.?!?\s*$',
            '', text, flags=re.IGNORECASE
        ).rstrip()
        
        # Append correct CTA if not present
        if "t.me/+qf7-zKuy2S5hYmYy" not in text:
            text = text.rstrip() + f"\n\n{CHANNEL_CTA}"
        
        return text

    def _build_channel_text(self, story_data: dict) -> str:
        """
        Builds a formatted Markdown channel post from story_data when LLM doesn't provide one.
        Uses rich Telegram Markdown formatting.
        """
        title = story_data.get("title", "История")
        slides = story_data.get("slides", [])
        
        parts = [f"# {title}\n"]
        
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
                    parts.append(f"> ✦ _{clean}_")
                question = slide.get("question", "")
                if question:
                    parts.append(f"💬 **{question}**")
        
        parts.append(f"\n{CHANNEL_CTA}")
        
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
            topic_title = first_line[:60].rsplit(' ', 1)[0].upper() + "..."
        else:
            topic_title = first_line.upper() if first_line else "НЕВЕРОЯТНАЯ ИСТОРИЯ"
        
        if not topic_title or len(topic_title) < 5:
            topic_title = "НЕВЕРОЯТНАЯ ИСТОРИЯ"

        # Target 4-5 story slides (total 6-8 with cover/ending/outro)
        total_sentences = len(sentences)
        target_slides = min(max(total_sentences // 2, 3), 5)  # 3-5 story slides
        
        # Distribute sentences evenly across slides
        slide_texts = []
        chunk_size = max(1, total_sentences // target_slides)
        
        for i in range(0, total_sentences, chunk_size):
            chunk = sentences[i:i + chunk_size]
            combined = " ".join(chunk)
            # STRICT limit: 280 chars per slide (≈40 words)
            if len(combined) > 280:
                # Cut at last sentence/word boundary
                cut = combined[:277].rsplit('. ', 1)[0]
                if len(cut) < 100:  # If cut too short, cut at word
                    cut = combined[:277].rsplit(' ', 1)[0]
                combined = cut + "..."
            slide_texts.append(combined)
        
        # Ensure max 5 story slides (total 8 with cover + ending + outro)
        if len(slide_texts) > 5:
            merged = " ".join(slide_texts[4:])
            if len(merged) > 280:
                merged = merged[:277].rsplit(' ', 1)[0] + "..."
            slide_texts = slide_texts[:4] + [merged]

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
            # Smart bold: find dramatic phrases, not random first words
            text_with_bold = self._smart_bold(text)
            
            if i == accent_idx:
                slides.append({
                    "type": "accent",
                    "text": text_with_bold,
                    "image_prompt": "Moody atmospheric scene, dark charcoal tones, dramatic lighting"
                })
            else:
                slides.append({
                    "type": "story",
                    "text": text_with_bold,
                    "image_prompt": ""
                })

        # 3. Ending — use last sentence as moral/conclusion  
        last_text = sentences[-1] if sentences else "Каждая история учит нас чему-то новому."
        ending_text = last_text if len(last_text) < 180 else last_text[:177] + "..."
        
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
        channel_text_parts = [f"# {topic_title}\n"]
        for text in slide_texts:
            clean = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
            channel_text_parts.append(clean)
        channel_text_parts.append(f"\n> ✦ _{ending_text}_")
        channel_text_parts.append(f"\n{CHANNEL_CTA}")

        return {
            "title": topic_title,
            "channel_text": "\n\n".join(channel_text_parts),
            "slides": slides
        }

    @staticmethod
    def _smart_bold(text: str) -> str:
        """
        Intelligently adds <b> tags to emotionally charged phrases,
        not random first words.
        """
        # Dramatic keywords to look for
        dramatic_patterns = [
            r'(оказал\w+ \w+)',
            r'(отказал\w+ \w+)',
            r'(потерял\w* \w+)',
            r'(обнаружил\w* \w+)',
            r'(выяснил\w+)',
            r'(признал\w+ \w+)',
            r'(не ожидал\w*)',
            r'(шокировал\w*)',
            r'(изменил\w* всё)',
            r'(никто не знал)',
            r'(всё пропало)',
            r'(невозможн\w+)',
            r'(решил\w* рискнуть)',
        ]
        
        for pattern in dramatic_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phrase = match.group(1)
                return text.replace(phrase, f"<b>{phrase}</b>", 1)
        
        # No dramatic phrase found — don't force bold
        return text
