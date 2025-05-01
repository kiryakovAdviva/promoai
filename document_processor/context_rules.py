# --- START OF FILE context_rules.py (Справочник констант v2) ---
# Этот файл содержит списки известных значений для метаданных RAG-чанков.
# Он используется модулем metadata_extractor.py для точного извлечения.

KNOWN_ENTITY_TYPES = [
    "process", "faq", "bonus_rule", "rule", "guide", "role_description", "metric_definition",
    "report_description", "form_instruction", "user_flow", "priority", "sla", "document_link", "table",
    "contact_list" # Добавим тип для списков контактов
]

KNOWN_RELATED_TOPICS = [
    "Promo", "Promo360", "VIP", "Payments", "Casino", "CRM", "Support", "Mostbet", "BetAndreas",
    "ASAP", "MWL", "MSD", "Antifraud", "CX", "Content", "Web-analytics", "Турниры", "Бонусы",
    "Платежи", "Игры", "Регламент", "Отчет", "Дашборд", "Форма", "Заявка", "Тикет"
]

KNOWN_PROCESS_STAGES = [
    "Инициация", "Оценка", "Приоритизация", "Продуктовая оценка", "Доработка брифа",
    "Согласование", "Антифрод", "Создание турнира", "Подготовка контента", "Макет и задачи",
    "Ежеквартальное планирование", "Подготовка к запуску", "Запуск", "A/B тест", "Мониторинг",
    "Информирование", "Исполнение", "Награда", "Постаналитика", "Подведение итогов", "Ретроспектива", "Отключение"
]

KNOWN_GEOS = [
    "ALL", "KZ", "TR", "AZ", "PT", "PL", "HU", "IN", "BD", "UA", "UZ", "NP", "SI", "PK", "RU", "CZ", "IT", "EN",
    "GLOBAL", "ROW", "BR", "GEO" # Добавим из предыдущих версий
]

KNOWN_CURRENCIES = [
    "RUB", "USD", "EUR", "TRY", "AZN", "INR", "KZT", "UZS", "BDT", "PKR", "LKR", "CZK", "PLN", "HUF", "UAH", "GEL" # Добавим валюты
]

KNOWN_DEPARTMENTS = [
    "Promo", "Casino", "Analytics", "Product", "VIP", "SMM", "CRM", "Content", "Support", "Payments",
    "CX", "MSD", "Tech", "Antifraud", "Web-analytics", "GOP", "HR", "Finance", "Legal", "Marketing",
    "Risk", "BI", "Development", "QA" # Добавим синонимы/варианты
]

KNOWN_METRICS = [
    "GGR", "NGR", "RR", "Retention", "CLTV", "LTV", "CR", "Conversion Rate", "Conversion", "Конверсия",
    "Average Deposit", "Avg. Deposit", "Средний депозит", "ROI", "ROMI",
    "ARPU", "ARPPU", "CAC", "Churn Rate", "Отток", "Active Users", "Активные игроки", "DAU", "WAU", "MAU",
    "Bet Count", "Количество ставок", "Avg Bet Size", "Средняя ставка",
    "Hold", "Margin", "Маржа", "Rake", "Рейк", "Bonus Cost", "Стоимость бонусов", "Turnover", "Оборот"
]

KNOWN_MECHANICS = [
    "Бонус", "Турнир", "Лотерея", "Цепочка", "Фриспины", "Фрибеты", "Промокод", "Ручная", "Авто",
    "ASAP", "Кэшбек", "Розыгрыш", "Миссия", "Джекпот", "Колесо фортуны", "Квест", "Giveaway",
    "Leaderboard", "Welcome Bonus", "Reload Bonus", "Бездепозитный бонус", "Депозитный бонус"
]

KNOWN_BONUS_TYPES = [
    "Бонусный пакет", "Фриспины", "Фрибет", "Промокод", "Кэшбек", "Реферальный бонус",
    "Деньги на счет", "Бездепозитный бонус", "Релоад бонус", "Страховка ставки", "Подарок",
    "Приветственный бонус", "Reload Bonus", "No Deposit Bonus", "Deposit Bonus", "Cash Bonus",
    "FS", "FB" # Короткие обозначения
]

KNOWN_PRIORITY_LEVELS = ["ASAP", "High", "Medium", "Low", "Backlog"]

KNOWN_SLA_VALUES = [ # Примеры конкретных значений, если они часто повторяются
    "3 рабочих дня", "5 рабочих дней", "10 рабочих дней", "72 часа", "24 часа",
    "1 рабочий день", "до конца недели", "до конца месяца", "до конца дня"
]

KNOWN_FORM_TYPES = [
    "Форма на аналитику", "Форма на бонус", "Jira тикет", "Asana форма", "Service Desk",
    "Форма на CRM", "Форма на дизайн", "Форма на разработку", "Форма на ручные бонусы",
    "Inbox 360", "Бриф на акцию", "Форма на отключение акции", "Заявка на аналитику",
    "Заявка на бонус", "Bonus Package Form", "Форма постановки задач", "Запрос на доступ"
]

KNOWN_TOOLS = [
    "Asana", "Confluence", "Google Docs", "Google Sheets", "Google Slides", "Jira", "Trello",
    "Miro", "Figma", "Slack", "Telegram", "Superset", "Power BI", "Metabase", "Grafana",
    "GrowthBook", "Admin Panel", "Админка", "Creatio", "Excel", "Word", "Outlook", "Service Desk"
]

KNOWN_RESPONSIBLE_KEYWORDS = [ # Используется для поиска строк с ответственными
    "ответственн", "контакт", "автор", "менеджер", "лид", "директор", "руководитель",
    "владелец", "исполнитель", "лпр", "head of", "lead", "manager", "director", "owner",
    "responsible", "contact person"
]

# Можно добавить другие списки, например, бренды, типы акций и т.д.

# --- END OF FILE context_rules.py ---