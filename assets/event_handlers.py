# --- START OF FILE assets/event_handlers.py (v4 - Adapted for new UI) ---
import gradio as gr
import time
import json
import traceback
import math
import os
import re
import datetime
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

# --- Импорты и Вспомогательные функции (остаются как в v3) ---
# ... (весь код до обработчиков событий) ...
try:
    from assistant.search_engine import semantic_search
    from assistant.embedder import embed_query
    from assistant.llm_client import ask_llm, SYSTEM_PROMPT
    from encryptor_tools import deobfuscate_text
except ImportError as e:
    print(f"❌ Ошибка импорта основных зависимостей в event_handlers.py: {e}. Используются заглушки.")
    def semantic_search(*args, **kwargs): return []
    def embed_query(*args, **kwargs): return None
    def ask_llm(*args, **kwargs): return "Ошибка: LLM недоступна."
    def deobfuscate_text(text, map_): return text
    SYSTEM_PROMPT = "SYSTEM_PROMPT_FALLBACK"

LOGS_DIR = "logs"; HISTORY_DIR = os.path.join(LOGS_DIR, "user_history")
os.makedirs(LOGS_DIR, exist_ok=True); os.makedirs(HISTORY_DIR, exist_ok=True)
CONTACT_KEYWORDS = ['контакт', 'связаться', 'email', 'почта', 'телеграм', 'tg', 'имя', 'фамилия', 'ответственный', 'роль', 'должность', 'лид', 'менеджер', 'директор', 'сотрудник', 'кто', 'человек']
SLA_KEYWORDS = ['sla', 'срок', 'время', 'дней', 'часов', 'недель', 'быстро', 'когда', 'долго']
PROCESS_KEYWORDS = ['процесс', 'этап', 'шаг', 'регламент', 'запуск', 'подготовка', 'аналитика', 'как']
TOOL_KEYWORDS = ['asana', 'jira', 'miro', 'confluence', 'инструмент', 'система', 'форма', 'доска', 'superset', 'power bi', 'metabase']
LINK_KEYWORDS = ['ссылка', 'url', 'адрес', 'перейти', 'где найти', 'форма', 'доска', 'документ', 'календарь', 'лого', 'плашк', 'роутинг']
KEY_LINK_KEYWORDS = {("inbox", "360"): "form.asana.com/?k=x7VsquZlamoAzBhkho0TkQ",("miro", "структура"): "miro.com/app/board/",("calendar", "календарь"): "confluence.dats.tech/display/MOS/calendar/",("msd", "инцидент"): "form.asana.com/?k=nc3ajhWt-yVWuXSG1U5m5w",("promo process", "процесс промо"): "app.asana.com/0/1207021300313272",("routing", "роутинг"): "form.asana.com/?k=0DSknHTYjf1cmHosatN3Zg",("logo", "лого", "плашк"): "form.asana.com/?k=nQkrYEdZO-TqK8bFVdw2ww",}

def get_history_filepath(username: str) -> str:
    safe_username = "".join(c for c in username if c.isalnum() or c in ('_', '-')).rstrip()
    return os.path.join(HISTORY_DIR, f"history_{safe_username}.json")
def load_user_history_dict(username: str) -> List[Dict[str, str]]:
    filepath = get_history_filepath(username);
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f: history = json.load(f)
            if isinstance(history, list) and all(isinstance(item, dict) and 'role' in item and 'content' in item for item in history): return history
            else: print(f"⚠️ Некорректный формат истории {filepath}."); return []
        except Exception as e: print(f"❌ Ошибка чтения истории {filepath}: {e}"); return []
    else: return []
def save_user_history_dict(username: str, history_dict: List[Dict[str, str]]):
    filepath = get_history_filepath(username);
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(history_dict, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"❌ Ошибка сохранения истории {filepath}: {e}")
def convert_dict_history_to_chatbot(history_dict: List[Dict[str, str]]) -> List[List[Optional[str]]]:
    chatbot_history = []; user_msg: Optional[str] = None
    for msg in history_dict:
        role = msg.get("role"); content = msg.get("content")
        if role == "user":
            if user_msg is not None: chatbot_history.append([user_msg, None])
            user_msg = content
        elif role == "assistant":
            if user_msg is not None: chatbot_history.append([user_msg, content]); user_msg = None
    if user_msg is not None: chatbot_history.append([user_msg, None])
    return chatbot_history
def convert_chatbot_history_to_dict(chatbot_history: List[List[Optional[str]]]) -> List[Dict[str, str]]:
    history_dict = []
    if not chatbot_history: return history_dict
    for pair in chatbot_history:
        user_content = str(pair[0]) if len(pair) >= 1 and pair[0] is not None else None
        assistant_content = str(pair[1]) if len(pair) >= 2 and pair[1] is not None else None
        if user_content: history_dict.append({"role": "user", "content": user_content})
        if assistant_content: history_dict.append({"role": "assistant", "content": assistant_content})
    return history_dict
def classify_query(query: str) -> Tuple[str, Dict]:
    query_lower = query.lower().strip();
    if not query_lower: return 'general', {}
    if any(kw in query_lower for kw in LINK_KEYWORDS):
        link_target = None; m = re.search(r"(?:ссылк[ау]|url|адрес)\s+(?:на\s+)?(?:форму\s+)?(?:доск[уи]\s+)?([\w\s\d\-\.\/]+(?:\s+[\w\d\-\.\/]+)*)", query_lower, re.I)
        if m: link_target = m.group(1).strip().lower()
        else:
            for kw_t, _ in KEY_LINK_KEYWORDS.items():
                 if any(skw in query_lower for skw in kw_t): link_target = " ".join(kw_t); break
            if not link_target:
                known = ['inbox 360', 'miro', 'calendar', 'msd', 'promo process', 'routing', 'asana', 'jira', 'confluence', 'superset', 'power bi', 'metabase', 'форма', 'доска']
                for t in known:
                    if t in query_lower: link_target = t; break
        if link_target: return 'link', {'link_target': link_target}
    if any(kw in query_lower for kw in CONTACT_KEYWORDS): return 'contact', {}
    if (re.search(r"[\w\.-]+@[\w\.-]+|@[\w\d\._]+", query_lower) or re.search(r"[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+", query)) and any(kw in query_lower for kw in ['кто', 'чей', 'ответств', 'роль', 'должн']): return 'contact', {}
    if any(kw in query_lower for kw in SLA_KEYWORDS): return 'sla', {}
    if any(kw in query_lower for kw in TOOL_KEYWORDS): return 'tool', {}
    if any(kw in query_lower for kw in PROCESS_KEYWORDS): return 'process', {}
    return 'general', {}
def calculate_heuristic_bonus(chunk: Dict, query_lower: str, query_type: str = 'general', link_target: Optional[str] = None) -> float:
    heuristic_score = 0.0;
    if not chunk or not isinstance(chunk, dict): return heuristic_score
    meta = chunk.get("meta", {}); text = chunk.get("text", "").lower(); is_structured = meta.get("table", False); is_excel = meta.get("source_type_raw", "").startswith("excel")
    if is_structured and query_type in ['contact', 'sla', 'general', 'link']: heuristic_score += 5.0
    if query_type == 'contact':
        multiplier = 0.5 if is_excel else 1.0;
        if any(kw in query_lower for kw in ['email', 'почта', 'телеграм', 'tg', 'телефон', 'связаться']): multiplier *= 1.5
        mentioned_name = None; name_match = re.search(r"([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?|@[a-zA-Z0-9._]+)", query_lower)
        if name_match: mentioned_name = name_match.group(1).lower()
        if meta.get("responsible"):
             resp_lower = str(meta["responsible"]).lower()
             if mentioned_name and mentioned_name in resp_lower: heuristic_score += 25 * multiplier
             else: heuristic_score += 10 * multiplier
        if re.search(r"[\w\.-]+@[\w\.-]+|@[\w\d\._]+", text): heuristic_score += 5 * multiplier
        keys_to_check = {'position', 'должность', 'name', 'имя', 'фамилия', 'email', 'почта', 'tg', 'telegram', 'contact', 'контакт', 'responsible', 'ответственный'}
        if is_structured:
            headers = [str(h).lower() for h in meta.get("columns", [])]
            if any(k in hdr for k in keys_to_check for hdr in headers): heuristic_score += 8 * multiplier
    elif query_type == 'sla':
        if meta.get("sla"): heuristic_score += 25
        if is_structured:
            headers = [str(h).lower() for h in meta.get("columns", [])]
            if any(k in hdr for k in ['sla', 'срок', 'время', 'duration'] for hdr in headers): heuristic_score += 15
        if 'инцидент' in query_lower and 'инцидент' in text: heuristic_score += 10
    elif query_type == 'process':
        if meta.get("stage"): heuristic_score += 15
        if meta.get("type") == "process": heuristic_score += 15
    elif query_type == 'tool':
        tool_in_query = next((tool for tool in meta.get("tools", []) if tool.lower() in query_lower), None) if meta.get("tools") else None
        form_in_query = next((form for form in meta.get("form_type", []) if form.lower() in query_lower), None) if meta.get("form_type") else None
        if tool_in_query or form_in_query: heuristic_score += 20
        elif meta.get("tools") or meta.get("form_type"): heuristic_score += 10
        if meta.get("type") == "form_instruction": heuristic_score += 10
    elif query_type == 'link':
        all_urls = set(meta.get("link", []));
        if all_urls: heuristic_score += 10
        if link_target:
            found_target_link = False
            for kw_tuple, pattern in KEY_LINK_KEYWORDS.items():
                 if link_target == " ".join(kw_tuple):
                     if any(pattern in url for url in all_urls): heuristic_score += 60; found_target_link = True; break
            if not found_target_link:
                 if any(link_target in url.lower() for url in all_urls): heuristic_score += 30
    try:
        q_words = set(re.findall(r'\b\w{3,}\b', query_lower)); t_words = set(re.findall(r'\b\w{3,}\b', text))
        common_words = q_words.intersection(t_words)
        if common_words: word_bonus_multiplier = 3 if query_type == 'general' else 5; heuristic_score += len(common_words) * word_bonus_multiplier
    except Exception: pass
    MAX_HEURISTIC_SCORE = 100.0; heuristic_score = min(heuristic_score, MAX_HEURISTIC_SCORE)
    if not isinstance(heuristic_score, (int, float)) or math.isnan(heuristic_score): return 0.0
    return float(heuristic_score)
def format_context(chunks_with_scores: List[Tuple[Dict[str, Any], float]]) -> str:
    if not chunks_with_scores: return "Контекст не найден."
    context_parts = []; all_unique_links = set()
    for i, (chunk, final_score) in enumerate(chunks_with_scores):
        if not isinstance(chunk, dict): continue
        meta = chunk.get("meta", {}); doc_name = meta.get("document_name", "N/A"); page = meta.get("page", "N/A"); chunk_id = chunk.get("id", "N/A"); chunk_text = chunk.get("text", "").strip()
        chunk_links = set(meta.get("link", [])); doc_links_meta = meta.get("document_links", [])
        if isinstance(doc_links_meta, list):
            for link_info in doc_links_meta:
                if isinstance(link_info, dict) and isinstance(link_info.get("url"), str): all_unique_links.add(link_info["url"])
        all_unique_links.update(chunk_links)
        header = f"--- Chunk [{i+1}] (Score: {final_score:.4f}) ---\n"; header += f"Источник: {doc_name}" + (f", Стр: {page}" if page != "N/A" else "") + f" (ID: {chunk_id})\n"
        meta_summary = {k: v for k, v in meta.items() if k in ['type', 'responsible', 'department', 'stage', 'geo', 'priority_level', 'sla', 'duration', 'mechanic', 'bonus_type', 'metric', 'form_type', 'wager', 'payout', 'currency', 'related_to', 'tools'] and v}
        if meta.get("table"): meta_summary['is_table'] = True
        if meta_summary:
            try: header += f"Метаданные: {json.dumps(meta_summary, ensure_ascii=False, default=str)}\n"
            except Exception as json_e: header += f"Метаданные: [Ошибка сериализации: {json_e}]\n"
        context_parts.append(header + "Текст:\n" + chunk_text + "\n" + "-"*20)
    if all_unique_links:
        context_parts.append("\n--- Найденные ссылки в контексте ---"); sorted_links = sorted(list(all_unique_links)); context_parts.extend(f"- {link}" for link in sorted_links); context_parts.append("-------------------------------------")
    return "\n\n".join(context_parts)
def log_interaction(username: str, message: str, results_chunks: List[Dict], scores_info: List[Tuple], final_answer: str, chosen_llm: str):
    # ... (код функции log_interaction) ...
    log_file_path = os.path.join(LOGS_DIR, "queries.log")
    try:
        query_type_for_log, _ = classify_query(message)
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*40}\n"); f.write(f"🕒 {datetime.datetime.now().isoformat()}\n"); f.write(f"👤 User: {username}\n")
            f.write(f"❓ Message: {message}\n"); f.write(f"🤖 LLM Used: {chosen_llm.upper()}\n")
            if results_chunks:
                f.write("🎯 Top relevant chunks found (after re-ranking):\n")
                scores_dict = {s_info[0]: {'final': s_info[1], 'semantic': s_info[2], 'heuristic': s_info[3]} for s_info in scores_info}
                for i, ch in enumerate(results_chunks):
                    chunk_id = ch.get('id', 'N/A'); chunk_scores = scores_dict.get(chunk_id, {'final': 0.0, 'semantic': 0.0, 'heuristic': 0.0})
                    f.write(f"--- Chunk {i+1} (ID: {chunk_id}) ---\n")
                    f.write(f"Final Score: {chunk_scores['final']:.4f} (Semantic: {chunk_scores['semantic']:.4f}, Heuristic: {chunk_scores['heuristic']:.2f}, QType: {query_type_for_log})\n")
                    meta_str = json.dumps(ch.get('meta', {}), ensure_ascii=False, indent=1, default=str); text_preview = (ch.get('text', '')[:150] + '...') if len(ch.get('text', '')) > 150 else ch.get('text', '')
                    f.write(f"Meta: {meta_str}\n"); f.write(f"Text Preview: {text_preview}\n")
            else: f.write("🎯 Relevant chunks: Not found or error.\n")
            f.write(f"🤖 Answer: {final_answer}\n"); f.write(f"{'='*40}\n")
    except Exception as e: print(f"⚠️ Ошибка записи лога: {e}"); traceback.print_exc()

# --- ОБРАБОТЧИКИ СОБЫТИЙ GRADIO ---

# def show_welcome(): # Анимация пока не используется
#     text = "Добро пожаловать! Я PromoAI..."
#     # ...
#     yield output

def switch_to_chat():
    """Возвращает команды для скрытия экрана приветствия и показа чата."""
    return gr.update(visible=False), gr.update(visible=True)

# --- ИЗМЕНЕНИЕ: handle_user_message теперь возвращает только 2 значения ---
def handle_user_message(message: str, history: List[List[Optional[str]]]) -> Tuple[List[List[Optional[str]]], gr.Textbox]:
    """Добавляет сообщение пользователя в историю и очищает поле ввода."""
    if not message or not message.strip():
        return history, gr.update() # Не очищаем ввод, если сообщение пустое
    history.append([message, None])
    return history, gr.update(value="") # Очищаем поле ввода
# --- Конец изменения ---

def handle_bot_response(
    history: List[List[Optional[str]]],
    request: gr.Request,
    app_state: Dict[str, Any]
    ):
    # ... (код функции handle_bot_response как был, включая вызов log_interaction) ...
    llm_choice = app_state.get("llm_choice", "gemini")
    safe_mode = app_state.get("safe_mode", False)
    obfuscation_map = app_state.get("obfuscation_map", {})

    username = request.username if request and hasattr(request, 'username') else "DefaultUser"
    print(f"\n💬 [{username}] Получен запрос на генерацию ответа...")
    if not history or not history[-1] or history[-1][1] is not None:
        print(f"⚠️ [{username}] Невалидная история."); return history
    message = history[-1][0]
    if not message: print(f"⚠️ [{username}] Пустое сообщение."); history[-1][1] = "Введите вопрос."; return history
    print(f"   ❓ Запрос: '{message}' (LLM: {llm_choice.upper()})")

    full_user_history_dict = load_user_history_dict(username)
    query_lower = message.lower().strip()
    query_type, search_filters = classify_query(query_lower)
    link_target = search_filters.get('link_target')
    print(f"📊 QType: {query_type}, Link Target: {link_target}")

    final_answer = "Не удалось обработать запрос."; top_chunks_for_context: List[Dict] = []; top_scores_for_logging: List[Tuple] = []

    try:
        print(f"  🔢 Embedding query..."); query_vector = embed_query(message)
        if query_vector is None: final_answer = "Ошибка эмбеддинга."; raise ValueError(final_answer)

        print(f"  🔍 Semantic search (top_k=20)..."); search_results_raw = semantic_search(query_vector, top_k=20)
        if not search_results_raw:
             print(f"  ⚠️ [{username}] No semantic results."); final_answer = "Информации не найдено."
             log_interaction(username, message, [], [], final_answer, llm_choice); history[-1][1] = final_answer
             if full_user_history_dict:
                 if not full_user_history_dict or full_user_history_dict[-1].get('role') == 'user': full_user_history_dict.append({'role': 'assistant', 'content': final_answer})
                 elif full_user_history_dict[-1].get('role') == 'assistant': full_user_history_dict[-1]['content'] = final_answer
             save_user_history_dict(username, full_user_history_dict); return history

        HEURISTIC_WEIGHT = 0.4; MAX_HEURISTIC_BONUS = 100.0; TOP_N_CONTEXT = 7
        def calculate_final_score_local(item: Tuple[Dict, float]) -> Tuple[float, float, float]:
            chunk, sem_score = item; heur_bonus = calculate_heuristic_bonus(chunk, query_lower, query_type, link_target)
            norm_heur = min(max(heur_bonus / MAX_HEURISTIC_BONUS, 0.0), 1.0) if MAX_HEURISTIC_BONUS > 0 else 0.0
            final_score = (1.0 + sem_score) * (1.0 + HEURISTIC_WEIGHT * norm_heur) - 1.0
            return (final_score, sem_score, heur_bonus) if not math.isnan(final_score) else (sem_score, sem_score, heur_bonus)

        ranked_results = sorted(search_results_raw, key=calculate_final_score_local, reverse=True)
        top_items = ranked_results[:TOP_N_CONTEXT]
        top_chunks_for_context = [item[0] for item in top_items]
        top_scores_for_logging = [(item[0].get('id','N/A'), *calculate_final_score_local(item)) for item in top_items]

        print(f"🏆 Top-{len(top_chunks_for_context)} after re-ranking (QType:{query_type}, W:{HEURISTIC_WEIGHT}):")
        scores_map = {info[0]: info[1] for info in top_scores_for_logging}
        for i, (chunk_id, final_sc, semantic_sc, heuristic_sc) in enumerate(top_scores_for_logging):
            ch = next((c for c in top_chunks_for_context if c.get('id') == chunk_id), {}); print(f"  {i+1}. Final:{final_sc:.4f} (Sem:{semantic_sc:.4f}, Heur:{heuristic_sc:.2f}) | ID:{chunk_id} | Doc:{ch.get('meta',{}).get('document_name')}")

        context = format_context([(chunk, scores_map.get(chunk.get('id'), 0.0)) for chunk in top_chunks_for_context])
        history_context_for_prompt = ""
        if len(full_user_history_dict) > 1:
            history_limit = 3; relevant_history_dict = full_user_history_dict[-(2 * history_limit + 1) : -1]
            if relevant_history_dict:
                 history_context_for_prompt = "\n\n--- ПРЕДЫДУЩИЙ ДИАЛОГ ---\n"
                 for item in relevant_history_dict:
                     role = "Пользователь" if item.get('role') == 'user' else "Ассистент"; content = str(item.get('content', '')).replace('{', '{{').replace('}', '}}')
                     history_context_for_prompt += f"{role}: {content}\n"
                 history_context_for_prompt += "-------------------------\n"

        prompt_instructions = ("Инструкция: Основываясь **строго** на предоставленном КОНТЕКСТЕ ДОКУМЕНТОВ и ПРЕДЫДУЩЕМ ДИАЛОГЕ (если есть), "
                               "дай ответ на ПОСЛЕДНИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ. Цитируй конкретные данные (email, TG вида @username, ссылки URL, SLA) если они есть в контексте. "
                               "Если релевантной информации для ответа нет, четко скажи, что информация не найдена.")
        prompt = f"""{prompt_instructions}

--- КОНТЕКСТ ДОКУМЕНТОВ ---
{context}
{history_context_for_prompt}
--- ПОСЛЕДНИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ ---
{message}

--- ТВОЙ ОТВЕТ ---
"""

        print(f"🤖 [{username}] Запрос к {llm_choice.upper()}..."); raw_answer = ask_llm(llm_choice, prompt, system_prompt=SYSTEM_PROMPT)
        print(f"✅ [{username}] Ответ получен от LLM.")
        final_answer = deobfuscate_text(raw_answer, obfuscation_map) if safe_mode else raw_answer

    except Exception as e_main:
        print(f"❌ [{username}] Error in generate_bot_response: {e_main}"); traceback.print_exc(); final_answer = "Внутренняя ошибка."

    log_interaction(username, message, top_chunks_for_context, top_scores_for_logging, final_answer, llm_choice) # Вызов здесь
    history[-1][1] = final_answer
    if not isinstance(full_user_history_dict, list): full_user_history_dict = []
    if not full_user_history_dict or full_user_history_dict[-1].get("content") != message: full_user_history_dict.append({'role': 'user', 'content': message})
    full_user_history_dict.append({'role': 'assistant', 'content': final_answer})
    MAX_HISTORY_LEN = 50
    if len(full_user_history_dict) > MAX_HISTORY_LEN: full_user_history_dict = full_user_history_dict[-MAX_HISTORY_LEN:]
    save_user_history_dict(username, full_user_history_dict)
    return history

# --- ИЗМЕНЕНИЕ: handle_clear_chat теперь возвращает только None ---
def handle_clear_chat(request: gr.Request):
    """Очищает историю чата."""
    username = request.username if request and hasattr(request, 'username') else "DefaultUser"
    print(f"🧹 [{username}] Очистка чата.")
    save_user_history_dict(username, [])
    # Очищаем только чатбот
    return None
# --- Конец изменения ---

# --- Аутентификация ---
user_credentials = {"Admin": "Admin", "User": "User"}
def authenticate(username, password):
    if username in user_credentials and user_credentials[username] == password: print(f"✅ [{username}] Аутентификация успешна."); return True
    else: print(f"❌ [{username}] Неудачная аутентификация."); return False

# --- END OF FILE assets/event_handlers.py ---