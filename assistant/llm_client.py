# llm_client.py - Поддержка Together AI и Google Gemini с выбором при запуске
import os
from dotenv import load_dotenv
import traceback

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Конфигурация Together AI ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
TOGETHER_MODEL_NAME = os.getenv("TOGETHER_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
together_client = None
together_configured = False
if TOGETHER_API_KEY:
    try:
        from together import Together # Импортируем здесь, чтобы не было ошибки, если не установлен
        together_client = Together(api_key=TOGETHER_API_KEY)
        together_configured = True
        print(f"✅ Together AI сконфигурирован. Модель по умолчанию: {TOGETHER_MODEL_NAME}")
    except ImportError:
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Библиотека 'together' не установлена. Together AI будет недоступен.")
    except Exception as e:
        print(f"❌ Ошибка при конфигурации Together AI: {e}")
else:
    print("⚠️ ПРЕДУПРЕЖДЕНИЕ: TOGETHER_API_KEY не найден в .env. Together AI будет недоступен.")


# --- Конфигурация Google Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-04-17")
genai = None
gemini_configured = False
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai # Импортируем здесь
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_configured = True
        print(f"✅ Gemini API сконфигурирован. Модель по умолчанию: {GEMINI_MODEL_NAME}")
    except ImportError:
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Библиотека 'google-generativeai' не установлена. Google Gemini будет недоступен.")
    except Exception as e:
        print(f"❌ Ошибка при конфигурации Gemini API: {e}")
        traceback.print_exc()
else:
    print("⚠️ ПРЕДУПРЕЖДЕНИЕ: GEMINI_API_KEY не найден в .env. Google Gemini будет недоступен.")

# --- Общий системный промпт (Улучшенная версия v2) ---
SYSTEM_PROMPT = (
    "Ты — точный и внимательный ассистент PromoAI. Твоя задача - отвечать на вопросы пользователя СТРОГО на основе предоставленных ниже фрагментов документов (контекста)."
    "\nОсновные правила:"
    "\n1. Используй **только** информацию из раздела 'КОНТЕКСТ ДОКУМЕНТОВ'. Не добавляй знания извне и ничего не выдумывай."
    "\n2. Если в контексте есть конкретные данные (имена, email, Telegram вида @username, ссылки URL, цифры SLA, названия форм/инструментов), **точно цитируй** их в ответе."
    "\n3. Если спрашивают контактные данные (email, TG, телефон) и они есть в контексте - предоставь их. Если их нет - четко скажи: 'В предоставленных документах [запрошенный контакт] не найден.'"
    "\n4. Если спрашивают ссылку на ресурс (форма, Miro, документ) и она есть в контексте - предоставь URL. Если упоминается ресурс, но ссылки нет, укажи это."
    "\n5. Если вопрос касается табличных данных, извлекай информацию из текста таблиц в контексте."
    "\n6. Если информация в контексте отсутствует или недостаточна для ответа, сообщи: 'На основе предоставленной информации я не могу точно ответить на ваш вопрос.'"
    "\n7. Учитывай предыдущий диалог (если он предоставлен), чтобы понимать контекст вопроса пользователя."
    "\n8. Отвечай кратко, по делу, без лишней информации."
)

# --- Функция для вызова Together AI ---
def _ask_together_internal(prompt: str, system_prompt: str = SYSTEM_PROMPT):
    if not together_configured or not together_client:
        return "Ошибка: Together AI не сконфигурирован или библиотека не установлена."
    print(f">> Отправка запроса в Together AI (модель: {TOGETHER_MODEL_NAME})...")
    try:
        response = together_client.chat.completions.create(
            model=TOGETHER_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1024,
            top_p=0.95
        )
        print(">> Запрос к Together AI выполнен.")
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Ошибка при запросе к Together API: {e}")
        traceback.print_exc()
        return f"Произошла ошибка при обращении к языковой модели Together AI: {e}"

# --- Функция для вызова Google Gemini ---
def _ask_gemini_internal(prompt: str, system_prompt: str = SYSTEM_PROMPT):
    if not gemini_configured or not genai:
        return "Ошибка: Gemini API не сконфигурирован или библиотека не установлена."
    print(f">> Отправка запроса в Gemini (модель: {GEMINI_MODEL_NAME})...")
    try:
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction=system_prompt
        )
        user_prompt = prompt
        generation_config = genai.types.GenerationConfig(
            temperature=0.4,
            top_p=0.95
        )
        safety_settings = {
            'HARM_CATEGORY_HARASSMENT': 'BLOCK_MEDIUM_AND_ABOVE',
            'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_MEDIUM_AND_ABOVE',
            'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_MEDIUM_AND_ABOVE',
            'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_MEDIUM_AND_ABOVE',
        }
        response = model.generate_content(
            user_prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        print(">> Запрос к Gemini выполнен.")
        # Обработка ответа (как в предыдущем примере)
        try:
            if response.text:
                print(">> Gemini вернул текст.")
                return response.text
            else:
                print(">> Gemini НЕ вернул текст. Проверяем причины...")
                if response.prompt_feedback.block_reason:
                    block_reason = response.prompt_feedback.block_reason
                    print(f"⚠️ Запрос к Gemini заблокирован. Причина: {block_reason}")
                    for rating in response.candidates[0].safety_ratings:
                         print(f"   - Категория: {rating.category}, Вероятность: {rating.probability}")
                    return f"Ответ не может быть сгенерирован из-за ограничений безопасности (Причина: {block_reason}). Попробуйте переформулировать запрос."
                else:
                    print("⚠️ Gemini вернул пустой ответ без явной причины блокировки.")
                    print(f"   Полный ответ: {response}")
                    return "Модель не смогла сгенерировать ответ на данный запрос (пустой ответ)."
        except ValueError:
             print(">> ValueError при доступе к response.text. Проверяем блокировку...")
             if response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason
                 print(f"⚠️ Запрос к Gemini заблокирован (ValueError). Причина: {block_reason}")
                 for rating in response.candidates[0].safety_ratings:
                     print(f"   - Категория: {rating.category}, Вероятность: {rating.probability}")
                 return f"Ответ не может быть сгенерирован из-за ограничений безопасности (Причина: {block_reason}). Попробуйте переформулировать запрос."
             else:
                 print("⚠️ Не удалось получить текст ответа Gemini (ValueError), причина блокировки не найдена.")
                 print(f"   Полный ответ: {response}")
                 return "Модель не вернула текстовый ответ, и причина неизвестна."
        except Exception as e_resp:
             print(f"❌ Ошибка при обработке ответа Gemini: {e_resp}")
             traceback.print_exc()
             return f"Произошла ошибка при обработке ответа Gemini: {e_resp}"

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ Ошибка при запросе к Gemini API: {e}")
        traceback.print_exc()
        return f"Произошла критическая ошибка при обращении к языковой модели Gemini: {e}"

# --- Основная функция вызова LLM (выбирает нужный метод) ---
def ask_llm(llm_choice: str, prompt: str, system_prompt: str = SYSTEM_PROMPT):
    """
    Вызывает выбранную LLM.
    llm_choice: 'together' или 'gemini'
    """
    if llm_choice == 'together':
        return _ask_together_internal(prompt, system_prompt)
    elif llm_choice == 'gemini':
        return _ask_gemini_internal(prompt, system_prompt)
    else:
        print(f"⚠️ Неизвестный выбор LLM: {llm_choice}. Используется заглушка.")
        return "Ошибка: Неизвестный тип LLM."

# Оставляем ask_together для возможной обратной совместимости или тестов,
# но теперь она просто вызывает ask_llm с выбором 'together'.
# В run_app.py будем использовать ask_llm.
def ask_together(prompt: str, system_prompt: str = SYSTEM_PROMPT):
     print("⚠️ Вызов устаревшей функции ask_together. Используйте ask_llm('together', ...).")
     return ask_llm('together', prompt, system_prompt)