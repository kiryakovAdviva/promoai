# --- START OF FILE embedder.py (Refactored v2 - Исправлены импорты typing) ---

import os
import numpy as np
from sentence_transformers import SentenceTransformer
import sys
# --- ДОБАВЛЕНО: Импорт типов ---
from typing import List, Optional
# --- Конец добавления ---

# --- Инициализация модели ---
MODEL_NAME = "BAAI/bge-m3"
model: Optional[SentenceTransformer] = None # Добавил тип для model
try:
    model = SentenceTransformer(MODEL_NAME)
    print(f"✅ Модель эмбеддингов '{MODEL_NAME}' успешно загружена.")
except Exception as e:
    sys.stderr.write(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить модель эмбеддингов '{MODEL_NAME}'. {e}\n")
    sys.stderr.write("   Убедитесь, что библиотека sentence-transformers установлена и есть доступ к Hugging Face Hub.\n")
    model = None

# --- Функции для эмбеддинга ---

def embed_query(query: str) -> Optional[np.ndarray]:
    """
    Генерирует эмбеддинг для поискового запроса пользователя.
    """
    if model is None:
        sys.stderr.write("❌ Ошибка: Модель эмбеддингов не загружена. Невозможно создать эмбеддинг запроса.\n")
        return None
    prompt = query
    try:
        embedding = model.encode(prompt, convert_to_numpy=True, normalize_embeddings=True)
        return embedding
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при генерации эмбеддинга для запроса: {e}\n")
        return None

def embed_texts(texts: List[str]) -> Optional[np.ndarray]:
    """
    Генерирует эмбеддинги для списка текстов (например, для индексации или сравнения).
    """
    if model is None:
        sys.stderr.write("❌ Ошибка: Модель эмбеддингов не загружена. Невозможно создать эмбеддинги текстов.\n")
        return None
    if not texts:
        # Возвращаем пустой numpy массив правильной формы (0 строк, N колонок)
        dim = get_embedding_dim()
        return np.empty((0, dim if dim else 1024), dtype=np.float32) if dim else np.empty((0, 1024), dtype=np.float32)

    try:
        embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при генерации эмбеддингов для текстов: {e}\n")
        return None

def get_embedding_dim() -> Optional[int]:
     """Возвращает размерность эмбеддингов модели."""
     if model:
         try:
            # Предпочтительный способ для SentenceTransformer
            dim = model.get_sentence_embedding_dimension()
            if dim: return dim
         except Exception:
             pass # Пробуем другие способы

     # Резервный вариант через конфигурацию
     try:
         if model and hasattr(model, 'config') and hasattr(model.config, 'hidden_size'):
              return model.config.hidden_size
     except Exception:
         pass

     # Запасной вариант для bge-m3
     if MODEL_NAME == "BAAI/bge-m3":
         print("⚠️ Не удалось определить размерность эмбеддингов автоматически, используется значение по умолчанию для bge-m3 (1024).")
         return 1024

     sys.stderr.write("❌ Ошибка: Не удалось определить размерность эмбеддингов.\n")
     return None

# --- END OF FILE embedder.py ---