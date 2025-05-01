# --- START OF FILE run_app.py (v17 - Fixed load_map import) ---
import gradio as gr
import os
from dotenv import load_dotenv
import sys
from typing import Dict # Добавил импорт Dict

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Импорты из других модулей ---
try:
    # --- ИЗМЕНЕНИЕ: Убрал load_map из этого импорта ---
    from assets.ui_components import create_ui
    from assets.event_handlers import authenticate
    # --- Конец изменения ---
    from assistant.llm_client import together_configured, gemini_configured
    from assistant.search_engine import initialize_search_engine
    # Проверяем наличие encryptor_tools для SAFE_MODE
    from encryptor_tools import deobfuscate_text # Просто проверяем импорт
    safe_mode_possible = True
except ImportError as e:
    print(f"❌ Критическая ошибка импорта в run_app.py: {e}")
    print("   Убедитесь, что структура папок верна и все зависимости установлены.")
    # Определяем заглушки, чтобы приложение могло запуститься с сообщением об ошибке
    def create_ui(state): return gr.Markdown("Ошибка загрузки UI компонентов.")
    def authenticate(u, p): return False
    def initialize_search_engine(): pass
    # def load_map(p): return {} # load_map здесь не нужен, он импортируется ниже
    together_configured = False; gemini_configured = False; safe_mode_possible = False

# --- Выбор LLM ---
llm_choice = ""
available_llms = []
if together_configured: available_llms.append("1. Together AI")
if gemini_configured: available_llms.append("2. Google Gemini")
if not available_llms: print("❌ Ни одна LLM не сконфигурирована!"); llm_choice = "none"
elif len(available_llms) == 1:
    choice_str = available_llms[0]; llm_choice = "together" if "Together" in choice_str else "gemini"
    print(f"✅ Обнаружена только одна LLM: {choice_str}. Используем её.")
else:
    print("Выберите LLM:"); print("\n".join(available_llms))
    while llm_choice not in ["together", "gemini"]:
        choice_input = input("Введите номер (1 или 2): ").strip()
        if choice_input == "1" and together_configured: llm_choice = "together"
        elif choice_input == "2" and gemini_configured: llm_choice = "gemini"
        else: print("Неверный ввод.")
print(f"▶️ Выбрана LLM: {llm_choice.upper() if llm_choice != 'none' else 'НЕТ'}")

# --- Настройка SAFE_MODE ---
SAFE_MODE = False
obfuscation_map: Dict = {}
if safe_mode_possible:
    answer = input("🔐 Включить SAFE_MODE (обфускация)? [Y/n]: ").strip().lower()
    SAFE_MODE = not (answer == "n")
    if SAFE_MODE:
        print("✅ SAFE_MODE ВКЛЮЧЕН")
        map_file_path = "data/output/obfuscation_map.json"
        print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ: SAFE_MODE требует специальной обработки данных. Загрузка карты из {map_file_path}...")
        if os.path.exists(map_file_path):
             try:
                 # --- ИЗМЕНЕНИЕ: Импортируем load_map здесь ---
                 from encryptor_tools import load_map
                 # --- Конец изменения ---
                 obfuscation_map = load_map(map_file_path); print(f"✅ Карта обфускации загружена.")
             except ImportError:
                  print(f"❌ Ошибка: Не удалось импортировать 'load_map' из encryptor_tools. SAFE_MODE отключен."); SAFE_MODE = False
             except Exception as e:
                  print(f"❌ Ошибка загрузки карты обфускации: {e}"); SAFE_MODE = False
        else: print(f"⚠️ Карта обфускации {map_file_path} не найдена. SAFE_MODE отключен."); SAFE_MODE = False
    else:
        print("✅ SAFE_MODE ВЫКЛЮЧЕН")
else:
    print("ℹ️ Модуль encryptor_tools не найден или не импортирован. SAFE_MODE недоступен.")


# --- Аутентификация (остается здесь) ---
# user_credentials определен внутри event_handlers.py, но authenticate импортирован
# user_credentials = {"Admin": "Admin", "User": "User"} # Можно удалить, если он не нужен глобально

# --- Инициализация ---
print("⏳ Инициализация поискового движка...")
initialize_search_engine()

# --- Запуск приложения ---
if __name__ == "__main__":
    launch_ready = True
    if llm_choice == "none": print("\n‼️ ЗАВЕРШЕНИЕ: LLM не сконфигурирована."); launch_ready = False

    if launch_ready:
        print(f"\n🚀 Запускаем Gradio (LLM: {llm_choice.upper()})...")
        initial_app_state = {
            "llm_choice": llm_choice,
            "safe_mode": SAFE_MODE,
            "obfuscation_map": obfuscation_map
        }
        ui = create_ui(initial_app_state)
        ui.launch(
            auth=authenticate,
            auth_message="Вход в PromoAI",
            inbrowser=True,
            share=True # Осторожно
        )
        print("ℹ️ Интерфейс запущен. Нажмите Ctrl+C для остановки.")

# --- END OF FILE run_app.py ---