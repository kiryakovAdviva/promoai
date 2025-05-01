# 🤖 PromoAI — Документальный Ассистент с RAG

PromoAI — это локальный ассистент, который обрабатывает PDF/DOCX/Excel документы, извлекает из них структурированную информацию, индексирует чанки с помощью FAISS и выполняет семантический поиск с помощью модели эмбеддингов. Ответы на запросы пользователя генерируются через выбранную LLM (Together AI или Gemini), строго на основе документационного контекста.

## 🚀 Возможности

- 📄 Поддержка PDF, DOCX, Excel-файлов
- 🔍 Семантический поиск с FAISS
- 🧠 Генерация ответов через TogetherAI или Gemini
- 📊 Автоматическое извлечение метаданных (этапы, SLA, ответственные, инструменты и т.д.)
- 🔐 SAFE_MODE — замена имен/контактов токенами для защиты данных
- 🎨 UI-интерфейс на Gradio

## 📁 Структура проекта

```text
├── run_processing.py           # Основной пайплайн обработки документов
├── run_embedder.py            # Создание эмбеддингов и FAISS индекса
├── run_app.py                 # Запуск Gradio-интерфейса
├── document_processor/
│   ├── document_parser.py     # Парсинг PDF, DOCX, Excel
│   ├── chunker.py             # Рекурсивный текстовый сплиттер
│   ├── metadata_extractor.py # Извлечение мета-данных
│   ├── common_utils.py        # Вспомогательные функции
│   └── context_rules.py       # Константы (гео, этапы, валюты и т.д.)
├── assistant/
│   ├── embedder.py            # Генерация эмбеддингов (BAAI/bge-m3)
│   ├── search_engine.py       # FAISS-поиск
│   └── llm_client.py          # Взаимодействие с LLM (Together, Gemini)
├── assets/
│   ├── ui_components.py       # Gradio UI
│   ├── event_handlers.py      # Обработка событий UI
│   └── style.css              # Стилизация интерфейса
├── encrypt_chunks.py          # Утилита обфускации текстов
├── encryptor_tools.py         # Замена имен/email/тулов на токены
├── config.json                # Конфигурация путей
├── data/
│   ├── input/                 # Входные документы
│   ├── output/                # Обработанные чанки и карта обфускации
│   └── cache/                 # Эмбеддинги и FAISS индекс
```

## ⚙️ Установка

```bash
pip install -r requirements.txt
# или вручную:
pip install sentence-transformers faiss-cpu gradio python-dotenv
```

> Также необходимо создать `.env` с ключами API для LLM:
```env
TOGETHER_API_KEY=your_key
GEMINI_API_KEY=your_key
```

## 📦 Запуск

1. **Обработка документов:**
```bash
python run_processing.py
```

2. **Создание эмбеддингов и индекса:**
```bash
python run_embedder.py
```

3. **Запуск интерфейса:**
```bash
python run_app.py
```

При первом запуске будет предложено выбрать модель и включить SAFE_MODE.

## 🛡 SAFE_MODE

- Активирует обфускацию (замену) имен, почт, Telegram-ников и названий инструментов.
- Используется для защиты чувствительных данных перед отправкой в LLM.

## 📌 Заметки

- Используемая модель эмбеддингов: `BAAI/bge-m3`
- Формат чанков: JSON с `text` и `meta` (document_name, type, geo, sla, responsible, etc.)
- Индексируется только `processed_chunks.json`

## 📞 Пример запросов

- "SLA для VIP акций в KZ"
- "Кто отвечает за запуск акций с CashBack?"
- "Ссылка на форму Inbox 360"
- "Какие этапы у Promo процесса?"

---

👨‍💻 Разработка: Ivan Kiryakov @touchpe
🔗 Лицензия: MIT
