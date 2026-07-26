# StoriesHub — Telegram Bot & Carousel Story Renderer

Автоматический генератор вирусных каруселей постов (1080×1350) для Threads, Instagram и Telegram Stories.
Создан для работы с минимальными затратами (0$ / мес на ИИ при использовании бесплатного лимита Gemini) и совместим как с локальным компьютером (Windows), так и с любым дешёвым VPS ($3/мес, 1 vCPU, 1 GB RAM).

---

## 🎨 Возможности

- **Нейросценарий**: Превращает тему или историю в сценарий из 8 слайдов с клиффхэнгерами, акцентными цитатами и вопросом к аудитории.
- **Пиксельный рендеринг (HTML/CSS + Playwright)**: Мрачный стильный дизайн, серебряная рамка, кастомный хэндл брединга (`@intstg_stories`), верстка с поддержкой выделений `<b>текста</b>`.
- **Иллюстрации на обложках**: Генерация мрачных реалистичных артов через FLUX / Pollinations.
- **Экспорт**: Готовый альманах слайдов в Telegram + выгрузка в 1 клик в `.zip` архив.

---

## 🚀 Быстрый запуск локально на Windows

### 1. Установка зависимостей
Убедитесь, что у вас установлен Python 3.10+:

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Настройка переменных `.env`
Создайте файл `.env` (скопируйте из `.env.example`):

```env
BOT_TOKEN=ваш_токен_телеграм_бота
GEMINI_API_KEY=ваш_ключ_gemini_api
BRAND_HANDLE=@intstg_stories
BRAND_NAME=StoriesHub
```

> **Где взять Gemini API Key?**
> Получите бесплатный API ключ за 1 минуту на [Google AI Studio](https://aistudio.google.com/).

### 3. Локальное тестирование рендеринга (без запуска бота)
Чтобы сразу проверить генерацию и посмотреть готовые карточки 1080x1350, запустите:

```bash
python test_render.py
```

Сгенерированные карточки сохранятся в папку `output/carousel_.../`.

### 4. Запуск Telegram Бота

```bash
python bot.py
```

---

## 🌐 Деплой на дешёвый VPS ($3-5 / месяц)

Бот оптимизирован для работы на слабых VPS (Ubuntu 22.04 LTS / Debian, 1 vCPU, 1 GB RAM).

### 1. Подготовка VPS и системных библиотек Playwright

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
# Установка системных библиотек для Headless Chrome
sudo npx playwright install-deps chromium
```

### 2. Клонирование и установка

```bash
cd /opt
git clone <ваш_репозиторий> my-bot
cd my-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Настройка файла подкачки SWAP (Рекомендуется для 1 GB RAM VPS)

Playwright браузеру требуется кратковременная память для скриншотов. Включите 1-2 ГБ SWAP:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 4. Автозапуск через Systemd Service

Создайте файл службы `/etc/systemd/system/stories-bot.service`:

```ini
[Unit]
Description=StoriesHub Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/opt/my-bot
ExecStart=/opt/my-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запустите бота:

```bash
sudo systemctl daemon-reload
sudo systemctl enable stories-bot
sudo systemctl start stories-bot
```

Проверить статус работы:

```bash
sudo systemctl status stories-bot
```

---

## 🛠️ Настройка дизайна и верстки
Вы можете легко редактировать шаблон карточек под ваш бренд:
- [slide.html](file:///a:/Dev/my-bot/core/templates/slide.html) — структура слайдов (шапка, цитаты, выводы).
- [style.css](file:///a:/Dev/my-bot/core/templates/style.css) — цвета, рамки, шрифты и эффекты тёмного фона.
