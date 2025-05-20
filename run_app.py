# --- START OF FILE run_app.py (v18 - Enforced SAFE_MODE) ---
import gradio as gr
import os
from dotenv import load_dotenv
import sys
from typing import Dict

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Импорты из других модулей ---
try:
    from assets.ui_components import create_ui
    from assets.event_handlers import authenticate
    from assistant.llm_client import together_configured, gemini_configured
    from assistant.search_engine import initialize_search_engine
    from encryptor_tools import deobfuscate_text, load_map
    print("✅ Все необходимые модули успешно загружены")
except ImportError as e:
    print(f"❌ Критическая ошибка импорта в run_app.py: {e}")
    print("   Убедитесь, что структура папок верна и все зависимости установлены.")
    sys.exit(1)

# --- Выбор LLM ---
llm_choice = ""
available_llms = []
if together_configured: available_llms.append("1. Together AI")
if gemini_configured: available_llms.append("2. Google Gemini")
if not available_llms: 
    print("❌ Ни одна LLM не сконфигурирована!")
    sys.exit(1)
elif len(available_llms) == 1:
    choice_str = available_llms[0]
    llm_choice = "together" if "Together" in choice_str else "gemini"
    print(f"✅ Обнаружена только одна LLM: {choice_str}. Используем её.")
else:
    print("Выберите LLM:")
    print("\n".join(available_llms))
    while llm_choice not in ["together", "gemini"]:
        choice_input = input("Введите номер (1 или 2): ").strip()
        if choice_input == "1" and together_configured: llm_choice = "together"
        elif choice_input == "2" and gemini_configured: llm_choice = "gemini"
        else: print("Неверный ввод.")
print(f"▶️ Выбрана LLM: {llm_choice.upper()}")

# --- Настройка SAFE_MODE ---
print("\n🔐 Инициализация SAFE_MODE...")
map_file_path = "data/output/obfuscation_map.json"
if not os.path.exists(map_file_path):
    print(f"❌ Критическая ошибка: Карта обфускации {map_file_path} не найдена.")
    print("   Запустите сначала encrypt_chunks.py для создания карты обфускации.")
    sys.exit(1)

try:
    obfuscation_map = load_map(map_file_path)
    print(f"✅ Карта обфускации загружена успешно")
except Exception as e:
    print(f"❌ Ошибка загрузки карты обфускации: {e}")
    sys.exit(1)

# --- Инициализация ---
print("\n⏳ Инициализация поискового движка...")
initialize_search_engine()

# --- Запуск приложения ---
if __name__ == "__main__":
    print(f"\n🚀 Запускаем Gradio (LLM: {llm_choice.upper()})...")
    initial_app_state = {
        "llm_choice": llm_choice,
        "safe_mode": True,  # SAFE_MODE всегда включен
        "obfuscation_map": obfuscation_map
    }
    ui = create_ui(initial_app_state)
    ui.launch(
        auth=authenticate,
        auth_message="Вход в PromoAI",
        inbrowser=True,
        share=False  # Отключаем share для безопасности
    )
    print("ℹ️ Интерфейс запущен. Нажмите Ctrl+C для остановки.")

# --- END OF FILE run_app.py ---