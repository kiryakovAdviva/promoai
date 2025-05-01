# --- START OF FILE metadata_extractor.py (v22 - Явные импорты, исправлен NameError) ---
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

# --- Импорты ---
CONTEXT_RULES_LOADED = False
try:
    # Попытка относительного импорта с явным перечислением
    from .common_utils import clean_text
    from .context_rules import (
        KNOWN_ENTITY_TYPES, KNOWN_RELATED_TOPICS, KNOWN_PROCESS_STAGES, KNOWN_GEOS,
        KNOWN_CURRENCIES, KNOWN_DEPARTMENTS, KNOWN_METRICS, KNOWN_MECHANICS,
        KNOWN_BONUS_TYPES, KNOWN_PRIORITY_LEVELS, KNOWN_SLA_VALUES,
        KNOWN_FORM_TYPES, KNOWN_TOOLS, KNOWN_RESPONSIBLE_KEYWORDS, KNOWN_CONTACTS
    )
    CONTEXT_RULES_LOADED = True
    # print("✅ Relative imports successful in metadata_extractor (v22).")

except ImportError:
    # Попытка прямого импорта с явным перечислением
    try:
        from common_utils import clean_text
        from context_rules import (
            KNOWN_ENTITY_TYPES, KNOWN_RELATED_TOPICS, KNOWN_PROCESS_STAGES, KNOWN_GEOS,
            KNOWN_CURRENCIES, KNOWN_DEPARTMENTS, KNOWN_METRICS, KNOWN_MECHANICS,
            KNOWN_BONUS_TYPES, KNOWN_PRIORITY_LEVELS, KNOWN_SLA_VALUES,
            KNOWN_FORM_TYPES, KNOWN_TOOLS, KNOWN_RESPONSIBLE_KEYWORDS, KNOWN_CONTACTS
        )
        CONTEXT_RULES_LOADED = True
        print("✅ context_rules lists and common_utils imported directly in metadata_extractor (v22).")
    except ImportError as e:
        sys.stderr.write(f"⚠️ WARNING: Failed to import context_rules lists or common_utils directly. Metadata extraction will be limited. Error: {e}\n")
        # Определяем ВСЕ списки как пустые, если импорт не удался ни одним способом
        KNOWN_ENTITY_TYPES, KNOWN_RELATED_TOPICS, KNOWN_PROCESS_STAGES, KNOWN_GEOS = [], [], [], []
        KNOWN_CURRENCIES, KNOWN_DEPARTMENTS, KNOWN_METRICS, KNOWN_MECHANICS = [], [], [], []
        KNOWN_BONUS_TYPES, KNOWN_PRIORITY_LEVELS, KNOWN_SLA_VALUES = [], [], []
        KNOWN_FORM_TYPES, KNOWN_TOOLS, KNOWN_RESPONSIBLE_KEYWORDS, KNOWN_CONTACTS = [], [], [], []
        # Заглушка для clean_text, если и он не импортировался
        if 'clean_text' not in locals():
            def clean_text(text): return str(text).strip() if text else ""

# --- Вспомогательные функции для извлечения ---

def _find_known_matches(text: str, known_list: List[str]) -> Set[str]:
    """Находит точные (регистронезависимые) совпадения из списка в тексте."""
    found = set()
    if not text or not known_list: return found
    sorted_list = sorted(known_list, key=len, reverse=True)
    text_lower = text.lower()
    known_list_lower_map = {item.lower(): item for item in sorted_list}
    for item_lower, item_original in known_list_lower_map.items():
        try:
            pattern = r"\b" + re.escape(item_lower) + r"\b"
            if re.search(pattern, text_lower):
                 found.add(item_original)
        except re.error: continue
    return found

def _extract_links(text: str) -> Set[str]:
    """Извлекает и очищает URL из текста."""
    links = set()
    if not text: return links
    url_pattern = r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>{}\[\]"]+|\((?:[^\s()<>"]+|(?:\([^\s()<>]+\)))*\))+(?:\((?:[^\s()<>"]+|(?:\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""
    try:
        raw_links = re.findall(url_pattern, text)
        for link_tuple in raw_links:
            link = link_tuple[0] if isinstance(link_tuple, tuple) else link_tuple
            cleaned_link = re.sub(r'[.,;!?\'"`<>]$', '', link).strip()
            if '.' in cleaned_link and len(cleaned_link) > 4:
                if not cleaned_link.startswith(('http://', 'https://')):
                    if cleaned_link.startswith('www.'):
                        cleaned_link = 'http://' + cleaned_link
                links.add(cleaned_link)
    except re.error as e:
         sys.stderr.write(f"⚠️ Regex error in _extract_links: {e}\n")
    return links

def _extract_responsible_names(text: str) -> Set[str]:
    """Извлекает имена, ассоциированные с ответственностью."""
    names = set()
    if not text or not CONTEXT_RULES_LOADED: return names

    name_pattern = r"\b([А-ЯЁ](?:[а-яё]+|\.)(?:\s+[А-ЯЁ][а-яё]+)?|[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.|[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)\b"
    contact_pattern = r"[\w\.-]+@[\w\.-]{2,}\.[\w]+|(?<![\w\.-])@[\w\d\._]{3,}"

    try:
        # 1. Имя после ключевого слова ответственности
        if KNOWN_RESPONSIBLE_KEYWORDS: # Проверка, что список загружен и не пуст
            responsible_regex = r"(?i)\b(?:" + "|".join(KNOWN_RESPONSIBLE_KEYWORDS) + r")[:\s]*"
            pattern1 = responsible_regex + r'\s*(' + name_pattern + ')'
            matches1 = re.findall(pattern1, text)
            for match in matches1:
                name_extracted = match if isinstance(match, str) else (match[-1] if isinstance(match, tuple) and len(match) > 0 and isinstance(match[-1], str) else None)
                if name_extracted:
                     name = name_extracted.strip()
                     if len(name) > 1: names.add(name)

        # 2. Имя перед контактом
        pattern2 = f'({name_pattern})\\s*[:(]?\\s*(?:{contact_pattern})'
        matches2 = re.findall(pattern2, text)
        for match in matches2:
            name_extracted = match if isinstance(match, str) else (match[0] if isinstance(match, tuple) and len(match) > 0 and isinstance(match[0], str) else None)
            if name_extracted:
                 name = name_extracted.strip()
                 if len(name) > 1: names.add(name)

        # 3. Имя после контакта
        pattern3 = f'(?:{contact_pattern})\\s*[:)]?\\s*({name_pattern})'
        matches3 = re.findall(pattern3, text)
        for match in matches3:
            name_extracted = match if isinstance(match, str) else (match[-1] if isinstance(match, tuple) and len(match) > 0 and isinstance(match[-1], str) else None)
            if name_extracted:
                 name = name_extracted.strip()
                 if len(name) > 1: names.add(name)

    except re.error as e:
         sys.stderr.write(f"⚠️ Regex error in _extract_responsible_names: {e}\n")

    # Ищем известные контакты (только если список загружен и не пуст)
    if CONTEXT_RULES_LOADED and KNOWN_CONTACTS:
        contacts_found = _find_known_matches(text, KNOWN_CONTACTS)
        for contact in contacts_found:
            if contact.startswith('@'):
                names.add(contact)

    return names

def _determine_entity_type(text: str, heading: Optional[str]) -> Optional[str]:
    """Определяет тип сущности на основе ключевых слов."""
    if not text and not heading: return None
    full_text_lower = ((heading.lower() if heading else "") + "\n" + text.lower()).strip()
    if not full_text_lower or not CONTEXT_RULES_LOADED: return None

    if _find_known_matches(full_text_lower, ["faq", "вопрос ответ", "чаво"]): return "faq"
    if _find_known_matches(full_text_lower, ["инструкция", "гайд", "руководство", "как сделать", "how to", "guide"]): return "guide"
    if _find_known_matches(full_text_lower, ["правило", "rule"]) and _find_known_matches(full_text_lower, ["бонус", "акция", "промо"]): return "bonus_rule"
    if _find_known_matches(full_text_lower, ["правило", "rule"]): return "rule"
    if _find_known_matches(full_text_lower, ["процесс", "process", "регламент", "workflow", "порядок", "схема взаимодействия"]): return "process"
    if _find_known_matches(full_text_lower, ["форма", "заявка", "тикет", "запрос", "постановка задачи", "бриф"]): return "form_instruction"
    if _find_known_matches(full_text_lower, ["роль", "role", "должность"]): return "role_description"
    if _find_known_matches(full_text_lower, ["метрика", "metric", "показатель", "kpi"]): return "metric_definition"
    if _find_known_matches(full_text_lower, ["отчет", "report", "дашборд", "dashboard"]): return "report_description"
    if _find_known_matches(full_text_lower, ["контакт", "contact list", "список контактов"]): return "contact_list"
    if _find_known_matches(full_text_lower, ["user flow", "путь пользователя"]): return "user_flow"

    return None

# --- Перенесенные Regex-функции ---

def _extract_sla(text: str) -> Set[str]:
    if not isinstance(text, str): return set()
    patterns = [
        r"(?i)(?:в течени[ие]|не более|до|порядка|около|максимум|минимум|приблизительно|за|не менее|от|срок)\s+(\d+[\.,]?\d*)\s*(?:-|до)?\s*(\d+[\.,]?\d*\s*)?(?:рабочих|раб\.?|календ\.?|к\.?)\s*(?:дней|дня|дн\.?|часов|час\.?|ч\.?|недель|нед\.?|месяцев|мес\.?)",
        r"(?i)\bSLA:?\s*(\d+[\.,]?\d*\s*(?:-|до)?\s*\d*[\.,]?\d*\s*(?:час|дн|раб|календ|недел|мес)[а-я\. ]*)",
        r"(?i)(?<!\d\s)(?<!\d)(?<!\d-)(\d+[\.,]?\d*)\s*(?:-|до)?\s*(\d+[\.,]?\d*\s*)?(?:рабочих|раб\.?|календ\.?|к\.?)\s*(?:дней|дня|дн\.?|часов|час\.?|ч\.?|недель|нед\.?|месяцев|мес\.?)(?!\s*\w)",
        r"(?i)\b(?:до\s+конца\s+(?:недели|месяца|дня))\b"
    ]
    found_slas = set()
    try:
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                sla_str = ""
                if isinstance(match, tuple):
                    parts = [str(part).strip() for part in match if part and str(part).strip()]
                    if parts: sla_str = " ".join(parts)
                elif isinstance(match, str):
                    sla_str = match.strip()
                if sla_str: found_slas.add(sla_str)
    except re.error as e:
        sys.stderr.write(f"⚠️ Regex error in _extract_sla: {e}\n")
    return found_slas

def _extract_duration(text: str) -> Set[str]:
    if not isinstance(text, str): return set()
    patterns = [
        r"\b(?:до|по)\s+(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})\b",
        r"\b(?:с|от)\s+(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})\s+(?:до|по)\s+(\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})\b",
        r"\b(\d+)\s*(?:h|час[а-я]*|ч)\b",
        r"\b(\d+)\s*(?:d|дн[ейя]|day[s]?)(?!\s*раб)",
        r"\b(\d+)\s*(?:недел[ьи]|week[s]?|нед\.?)\b",
        r"\b(\d+)\s*(?:месяц[а-яев]*|month[s]?|мес\.?)\b",
        r"\b(\d)\s*(?:квартал|quarter)\b",
        r"\bQ([1-4])\b",
        r"(?i)\b(?:бессрочно|постоянно|навсегда|permanent|unlimited)\b",
        r"(?i)\b(?:в\s+течени[ие]\s+жизни\s+аккаунта)\b",
    ]
    durations = set()
    try:
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                duration_str = ""
                if isinstance(match, tuple):
                     parts = [str(part).strip() for part in match if part and str(part).strip()]
                     if len(parts) == 2: duration_str = f"с {parts[0]} по {parts[1]}"
                     elif len(parts) == 1: duration_str = parts[0]
                elif isinstance(match, str):
                    duration_str = match.strip()
                if not duration_str: continue
                normalized = duration_str
                if re.match(r"^\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4}$", duration_str): normalized = f"до {duration_str}"
                elif " с " in duration_str and " по " in duration_str: pass
                elif re.search(r"\d+\s*(?:h|час)", duration_str, re.I): pass
                elif re.search(r"\d+\s*(?:d|дн|day)", duration_str, re.I): pass
                elif re.search(r"\d+\s*(?:недел|week)", duration_str, re.I): pass
                elif re.search(r"\d+\s*(?:месяц|month)", duration_str, re.I): pass
                elif re.search(r"\d\s*квартал", duration_str, re.I): pass
                elif re.search(r"Q[1-4]", duration_str, re.I): pass
                elif re.search(r"бессрочно|постоянно|навсегда|permanent|unlimited", duration_str, re.I): normalized = "Бессрочно"
                elif re.search(r"жизни\s+аккаунта", duration_str, re.I): normalized = "Время жизни аккаунта"
                if normalized: durations.add(normalized.strip())
    except re.error as e:
        sys.stderr.write(f"⚠️ Regex error in _extract_duration: {e}\n")
    sla_list = _extract_sla(text)
    final_durations = {d for d in durations if d not in sla_list}
    return final_durations


def _extract_wager(text: str) -> Set[str]:
    if not isinstance(text, str): return set()
    patterns = [
        r"(?i)(?:wager|вейджер|отыгрыш|отыграть|wagering|прокрутить)\s*[:=\s]*([xXхХ]?\s?\d+)",
        r"(?i)\b([xXхХ]\s?\d+)\b",
        r"(?i)\b(real\s*\+\s*bonus)\b",
        r"(?i)\b(без\s*вейджер|без\s*отыгрыш|no\s*wager|0x|x0)\b"
    ]
    found_wagers = set()
    try:
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                wager_part = match if isinstance(match, str) else (match[0] if isinstance(match, tuple) and match else None)
                if not wager_part: continue
                wager_str = wager_part.replace(" ", "").upper()
                if "БЕЗВЕЙДЖЕР" in wager_str or "NOWAGER" in wager_str or wager_str == "X0" or wager_str == "0X":
                    found_wagers.add("x0")
                elif "REAL+BONUS" in wager_str:
                    found_wagers.add("real+bonus")
                else:
                    wager_val = re.sub(r"[^XХ\d]", "", wager_str)
                    if wager_val and any(char.isdigit() for char in wager_val):
                        wager_val = wager_val.replace('Х','X')
                        if not wager_val.startswith('X'): wager_val = 'x' + wager_val
                        else: wager_val = 'x' + wager_val[1:]
                        found_wagers.add(wager_val)
    except re.error as e:
        sys.stderr.write(f"⚠️ Regex error in _extract_wager: {e}\n")
    return found_wagers

def _extract_payout(text: str) -> Set[str]:
     if not isinstance(text, str): return set()
     patterns = [
          r"(?i)\b(?:max.*win|payout|макс.*выигрыш|выплат[аы]|лимит выигрыша|максимальный вывод)\s*[:=]?\s*([xXхХ]\s?\d+)\b",
          r"(?i)\b(?:max.*win|payout|макс.*выигрыш|выплат[аы]|лимит выигрыша|максимальный вывод)\s*[:=]?\s*(\d+[\.,]?\d*\s*(?:AZN|RUB|EUR|TRY|USD|INR|KZT|UZS|BDT|PKR|LKR|CZK|PLN|HUF|UAH|GEL|[€₽₺$]))\b"
     ]
     found_payouts = set()
     try:
         for pattern in patterns:
             matches = re.findall(pattern, text)
             for match in matches:
                 if not isinstance(match, str): continue
                 payout_str = match.strip().replace(" ", "").upper()
                 if not payout_str: continue
                 if payout_str.startswith(('X','Х')):
                     payout_str = payout_str.replace('Х','X')
                     if payout_str == 'X': continue
                     found_payouts.add('x' + payout_str[1:])
                 else:
                     normalized_cur = payout_str
                     for sym, code in {'€': 'EUR', '₽': 'RUB', '₺': 'TRY', '$': 'USD'}.items():
                          normalized_cur = normalized_cur.replace(sym, code)
                     # Исправляем удаление точки как разделителя тысяч
                     normalized_cur = re.sub(r"(\d)[,.](\d{3})", r"\1\2", normalized_cur) # Удаляем только если 3 цифры после
                     num_part = re.match(r"(\d+)", normalized_cur)
                     cur_part = re.search(r"([A-Z]{3})$", normalized_cur)
                     if num_part and cur_part:
                          found_payouts.add(f"{num_part.group(1)}{cur_part.group(1)}")
     except re.error as e:
         sys.stderr.write(f"⚠️ Regex error in _extract_payout: {e}\n")
     return found_payouts


def _extract_goals(text: str) -> Set[str]:
    if not isinstance(text, str): return set()
    goals = set()
    try:
        pattern_explicit = r"(?i)(?:^|\n)\s*(?:цель|goal|задача|expected\s*result)[:\s]+([^\n]+)"
        explicit_goals = [g.strip() for g in re.findall(pattern_explicit, text)]
        goals.update(g for g in explicit_goals if len(g) > 5)
        patterns_action = [
            r"(?i)\b(?:рост|увелич[а-я]+|привлеч[а-я]+|повышен[а-я]+)\s+([\w\s.,-]+?)(?:[\.,;]|$|\n)",
            r"(?i)\b(?:снижен[а-я]+|уменьшен[а-я]+|сокращен[а-я]+)\s+([\w\s.,-]+?)(?:[\.,;]|$|\n)"
        ]
        for p_action in patterns_action:
            matches_action = re.findall(p_action, text)
            for match in matches_action:
                if not isinstance(match, str): continue
                goal_text = match.strip(" .,;")
                if 5 < len(goal_text) < 100 :
                     goals.add(goal_text.capitalize())
    except re.error as e:
        sys.stderr.write(f"⚠️ Regex error in _extract_goals: {e}\n")
    return goals

# --- Основная функция извлечения метаданных (v22) ---
def extract_metadata(
    chunk_text: Optional[str],
    document_name: str,
    source_type: str, # Технический тип источника ('pdf_text_chunk', и т.д.)
    page_number: Optional[int] = None,
    table_headers: Optional[List[str]] = None,
    table_data: Optional[List[Dict[str, Any]]] = None,
    excel_row_data: Optional[Dict[str, Any]] = None, # Исправлен тип Dict[str, Any]
    document_hyperlinks: Optional[List[Dict]] = None,
    current_heading: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Извлекает метаданные согласно "идеальной структуре", используя списки KNOWN_* и Regex.
    """
    meta: Dict[str, Any] = {"document_name": document_name}
    if page_number: meta["page"] = page_number

    text_to_analyze = chunk_text if chunk_text else ""
    is_table_or_excel = 'table' in source_type or 'excel' in source_type

    meta_candidates: Dict[str, Set[str]] = defaultdict(set)
    responsible_names: Set[str] = set()
    all_links: Set[str] = set()
    found_entity_type: Optional[str] = None

    # --- 1. Извлечение из текста чанка ---
    if text_to_analyze:
        all_links.update(_extract_links(text_to_analyze))

        if CONTEXT_RULES_LOADED:
            meta_candidates["stage"] = _find_known_matches(text_to_analyze, KNOWN_PROCESS_STAGES)
            meta_candidates["geo"] = _find_known_matches(text_to_analyze, KNOWN_GEOS)
            meta_candidates["currency"] = _find_known_matches(text_to_analyze, KNOWN_CURRENCIES)
            meta_candidates["department"] = _find_known_matches(text_to_analyze, KNOWN_DEPARTMENTS)
            meta_candidates["metric"] = _find_known_matches(text_to_analyze, KNOWN_METRICS)
            meta_candidates["mechanic"] = _find_known_matches(text_to_analyze, KNOWN_MECHANICS)
            meta_candidates["bonus_type"] = _find_known_matches(text_to_analyze, KNOWN_BONUS_TYPES)
            meta_candidates["priority_level"] = _find_known_matches(text_to_analyze, KNOWN_PRIORITY_LEVELS)
            meta_candidates["sla"].update(_find_known_matches(text_to_analyze, KNOWN_SLA_VALUES))
            meta_candidates["form_type"] = _find_known_matches(text_to_analyze, KNOWN_FORM_TYPES)
            meta_candidates["tools"] = _find_known_matches(text_to_analyze, KNOWN_TOOLS)
            meta_candidates["related_to"].update(_find_known_matches(text_to_analyze, KNOWN_RELATED_TOPICS))
            responsible_names.update(_extract_responsible_names(text_to_analyze))
            found_entity_type = _determine_entity_type(text_to_analyze, current_heading)

        meta_candidates["sla"].update(_extract_sla(text_to_analyze))
        meta_candidates["duration"] = _extract_duration(text_to_analyze)
        meta_candidates["wager"] = _extract_wager(text_to_analyze)
        meta_candidates["payout"] = _extract_payout(text_to_analyze)
        meta_candidates["goal"] = _extract_goals(text_to_analyze)

    # --- 2. Извлечение из структурированных данных (Excel/Таблица) ---
    if is_table_or_excel:
        meta["table"] = True
        if table_headers: meta["columns"] = table_headers

        combined_table_text = ""
        data_source = {}
        if excel_row_data:
            combined_table_text = ". ".join(f"{k}: {v}" for k, v in excel_row_data.items())
            data_source = excel_row_data
        elif table_data:
            combined_table_text = "\n".join([" | ".join(str(cell) for cell in row.values()) for row in table_data])

        if combined_table_text:
            responsible_names.update(_extract_responsible_names(combined_table_text))
            all_links.update(_extract_links(combined_table_text))
            if CONTEXT_RULES_LOADED:
                meta_candidates["metric"].update(_find_known_matches(combined_table_text, KNOWN_METRICS))
                meta_candidates["mechanic"].update(_find_known_matches(combined_table_text, KNOWN_MECHANICS))
                meta_candidates["bonus_type"].update(_find_known_matches(combined_table_text, KNOWN_BONUS_TYPES))
                meta_candidates["department"].update(_find_known_matches(combined_table_text, KNOWN_DEPARTMENTS))

        if data_source:
            resp_keys = {'manager', 'responsible', 'ответственный', 'куратор', 'owner', 'лид', 'фио', 'имя'}
            for k, v in data_source.items():
                if str(k).lower() in resp_keys and isinstance(v, str) and v.strip():
                    responsible_names.add(v.strip())
                if isinstance(v, str) and v.startswith("http"): all_links.add(v)

    # --- 3. Финализация и сборка meta ---
    if found_entity_type: meta["type"] = found_entity_type
    if all_links: meta["link"] = sorted(list(all_links))

    first_responsible = next((name for name in sorted(list(responsible_names)) if name), None)
    if first_responsible: meta["responsible"] = first_responsible

    for key, candidates in meta_candidates.items():
        if candidates:
            # Приводим к строке и убираем пустые перед добавлением
            valid_candidates = {str(c).strip() for c in candidates if c and str(c).strip()}
            if not valid_candidates: continue

            if key == "priority_level":
                priority_order = {"ASAP": 5, "High": 4, "Medium": 3, "Low": 2, "Backlog": 1}
                best_priority = max(valid_candidates, key=lambda p: priority_order.get(p, 0), default=None)
                if best_priority: meta[key] = best_priority # Добавляем только если нашли
            else:
                 meta[key] = sorted(list(valid_candidates))

    related_items = set()
    related_items.update(meta_candidates["related_to"])
    if "department" in meta: related_items.update(meta["department"])
    if "mechanic" in meta: related_items.update(meta["mechanic"])
    if "geo" in meta: related_items.update(meta["geo"])
    if "priority_level" in meta: related_items.add(meta["priority_level"])
    if "type" in meta: related_items.add(meta["type"])
    related_items = {item for item in related_items if item and str(item).strip()}
    if related_items: meta["related_to"] = sorted(list(related_items))

    return meta

# --- END OF FILE metadata_extractor.py ---