# --- START OF FILE assets/ui_components.py (v7 - Input Container Fix) ---
import gradio as gr
from typing import Dict, Any, Tuple, List, Optional
import os

# --- Импорт обработчиков ---
try:
    from assets.event_handlers import (
        switch_to_chat, handle_user_message,
        handle_bot_response, handle_clear_chat
    )
except ImportError as e:
    print(f"❌ Ошибка импорта обработчиков в ui_components.py: {e}. Используются заглушки.")
    def switch_to_chat(): return gr.update(), gr.update()
    def handle_user_message(*args): return [], gr.update()
    def handle_bot_response(*args): return []
    def handle_clear_chat(*args): return None

# --- Структура UI ---

def create_welcome_screen() -> Tuple[gr.Column, gr.Button]:
    with gr.Column(visible=True, elem_id="welcome_screen") as welcome_screen:
        gr.Markdown("# Hi, Admin", elem_id="welcome_header")
        gr.Markdown("What can I help you with?", elem_id="welcome_subheader")
        gr.Markdown("Choose a prompt below or write your own to start chatting.", elem_id="welcome_prompt_info")
        start_btn = gr.Button("Начать чат", variant="primary")
    return welcome_screen, start_btn

def create_chat_screen() -> Dict[str, Any]:
    components: Dict[str, Any] = {}
    with gr.Column(visible=False, elem_id="chat_screen") as chat_screen:
        components["chat_screen_column"] = chat_screen
        components["title"] = gr.Markdown("## 🤖 PromoAI Ассистент", elem_id="chat_title")
        components["chatbot"] = gr.Chatbot(elem_id="chatbot", label="PromoAI", height=600, show_copy_button=True, layout="panel", avatar_images=(None, "assets/bot_avatar.png"))
        with gr.Row(elem_id="input_row"):
            components["msg_input"] = gr.Textbox(
                elem_id="user_input", placeholder="Ask a question or make a request...", label="Ввод",
                lines=1, scale=7, show_label=False,
                # --- ИЗМЕНЕНИЕ: Вернули container=True (по умолчанию) ---
                container=True
            )
            components["send_button"] = gr.Button("Отправить", variant="primary", scale=1, min_width=100)

        components["examples_area"] = gr.Examples(
             label="Примеры", examples=[["Email Максима Рощины?"], ["SLA отдела CX при инцидентах?"], ["Ссылка на форму Promo Inbox 360?"], ["Структура отдела на Miro?"], ["Кто отвечает за запуск платежных акций?"]],
             inputs=[components["msg_input"]], elem_id="examples", examples_per_page=10
         )
        with gr.Row(elem_id="clear_button_row"):
            components["clear_button"] = gr.Button("🗑️ Очистить чат", elem_id="clear_button")

    return components

# --- Регистрация событий ---
def register_event_handlers(
    welcome_screen: gr.Column, start_btn: gr.Button,
    chat_components: Dict[str, Any], app_state: gr.State
    ):
    chat_screen_col = chat_components["chat_screen_column"]
    chatbot = chat_components["chatbot"]
    msg_input = chat_components["msg_input"]
    send_button = chat_components["send_button"]
    clear_button = chat_components["clear_button"]

    start_btn.click(fn=switch_to_chat, inputs=None, outputs=[welcome_screen, chat_screen_col], queue=False)

    trigger_events = [msg_input.submit, send_button.click]
    for event in trigger_events:
        event(fn=handle_user_message, inputs=[msg_input, chatbot], outputs=[chatbot, msg_input], queue=False
             ).then(fn=handle_bot_response, inputs=[chatbot, app_state], outputs=[chatbot], api_name="generate_response")

    clear_button.click(fn=handle_clear_chat, inputs=None, outputs=[chatbot], queue=False)

# --- Основная функция построения UI ---
def create_ui(initial_app_state: Dict) -> gr.Blocks:
    current_dir = os.path.dirname(__file__)
    css_path = os.path.join(current_dir, "style.css")
    custom_css = None
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f: custom_css = f.read()
            print(f"✅ CSS загружен из {css_path}")
        except Exception as e: print(f"⚠️ Не удалось загрузить CSS из {css_path}: {e}")
    else: print(f"⚠️ Файл CSS не найден по пути: {css_path}")

    with gr.Blocks(title="PromoAI Ассистент", css=custom_css, theme=gr.themes.Default()) as demo:
        app_state = gr.State(value=initial_app_state)
        welcome_screen, start_btn = create_welcome_screen()
        chat_components = create_chat_screen()
        register_event_handlers(welcome_screen, start_btn, chat_components, app_state)
    return demo

# --- END OF FILE assets/ui_components.py ---