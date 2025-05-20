# --- START OF FILE embedder.py (Refactored v3 - Added preprocessing and batching) ---

import os
import numpy as np
from sentence_transformers import SentenceTransformer
import sys
import re
import json
from typing import List, Optional, Dict, Any
from tqdm import tqdm

# --- Инициализация модели ---
MODEL_NAME = "BAAI/bge-m3"
model: Optional[SentenceTransformer] = None

def preprocess_text(text: str) -> str:
    """Предварительная обработка текста перед эмбеддингом"""
    if not text:
        return ""
    # Удаление специальных символов
    text = re.sub(r'[^\w\s]', ' ', text)
    # Нормализация пробелов
    text = ' '.join(text.split())
    # Приведение к нижнему регистру
    text = text.lower()
    return text

def initialize_model() -> bool:
    """Инициализация модели эмбеддингов"""
    global model
    try:
        model = SentenceTransformer(MODEL_NAME)
        print(f"✅ Модель эмбеддингов '{MODEL_NAME}' успешно загружена.")
        return True
    except Exception as e:
        sys.stderr.write(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить модель эмбеддингов '{MODEL_NAME}'. {e}\n")
        sys.stderr.write("   Убедитесь, что библиотека sentence-transformers установлена и есть доступ к Hugging Face Hub.\n")
        model = None
        return False

# Инициализируем модель при импорте
initialize_model()

def embed_query(query: str) -> Optional[np.ndarray]:
    """
    Генерирует эмбеддинг для поискового запроса пользователя.
    """
    if model is None:
        sys.stderr.write("❌ Ошибка: Модель эмбеддингов не загружена. Невозможно создать эмбеддинг запроса.\n")
        return None
    
    try:
        # Предварительная обработка запроса
        processed_query = preprocess_text(query)
        if not processed_query:
            sys.stderr.write("❌ Ошибка: Пустой запрос после предварительной обработки.\n")
            return None
            
        embedding = model.encode(processed_query, convert_to_numpy=True, normalize_embeddings=True)
        return embedding
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при генерации эмбеддинга для запроса: {e}\n")
        return None

def embed_texts_batched(texts: List[str], batch_size: int = 32) -> Optional[np.ndarray]:
    """
    Генерация эмбеддингов батчами для оптимизации памяти.
    """
    if model is None:
        sys.stderr.write("❌ Ошибка: Модель эмбеддингов не загружена. Невозможно создать эмбеддинги текстов.\n")
        return None
        
    if not texts:
        dim = get_embedding_dim()
        return np.empty((0, dim if dim else 1024), dtype=np.float32) if dim else np.empty((0, 1024), dtype=np.float32)

    try:
        # Предварительная обработка всех текстов
        print("  Предварительная обработка текстов...")
        processed_texts = []
        with tqdm(total=len(texts), desc="Обработка текстов", unit="текст") as pbar:
            for text in texts:
                # Предполагаем, что все тексты уже валидны, так как они прошли фильтрацию в run_embedder.py
                processed_text = preprocess_text(text)
                processed_texts.append(processed_text)  # Добавляем все тексты, даже если они стали пустыми после обработки
                pbar.update(1)
        
        # Генерация эмбеддингов батчами
        print("  Генерация эмбеддингов...")
        all_embeddings = []
        num_batches = (len(processed_texts) + batch_size - 1) // batch_size
        
        with tqdm(total=num_batches, desc="Генерация эмбеддингов", unit="батч") as pbar:
            for i in range(0, len(processed_texts), batch_size):
                batch = processed_texts[i:i + batch_size]
                batch_embeddings = model.encode(batch, convert_to_numpy=True, normalize_embeddings=True)
                all_embeddings.append(batch_embeddings)
                pbar.update(1)
        
        # Объединение всех батчей
        print("  Объединение результатов...")
        embeddings = np.vstack(all_embeddings)
        
        # Валидация результатов
        if not validate_embeddings(embeddings, processed_texts):
            sys.stderr.write("❌ Ошибка: Валидация эмбеддингов не пройдена.\n")
            return None
            
        # Логирование статистики
        log_embedding_stats(embeddings, processed_texts)
        
        return embeddings
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при генерации эмбеддингов для текстов: {e}\n")
        return None

def validate_embeddings(embeddings: np.ndarray, texts: List[str]) -> bool:
    """Проверка качества эмбеддингов"""
    if embeddings.shape[0] != len(texts):
        sys.stderr.write(f"❌ Ошибка: Несоответствие количества эмбеддингов ({embeddings.shape[0]}) и текстов ({len(texts)}).\n")
        return False
        
    # Проверка на NaN и Inf
    if np.isnan(embeddings).any() or np.isinf(embeddings).any():
        sys.stderr.write("❌ Ошибка: Обнаружены NaN или Inf значения в эмбеддингах.\n")
        return False
        
    # Проверка нормализации
    norms = np.linalg.norm(embeddings, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-6):
        sys.stderr.write("❌ Ошибка: Эмбеддинги не нормализованы.\n")
        return False
        
    return True

def log_embedding_stats(embeddings: np.ndarray, texts: List[str]):
    """Логирование статистики эмбеддингов"""
    stats = {
        'total_vectors': len(embeddings),
        'dimension': embeddings.shape[1],
        'mean_norm': float(np.mean(np.linalg.norm(embeddings, axis=1))),
        'std_norm': float(np.std(np.linalg.norm(embeddings, axis=1))),
        'empty_texts': sum(1 for t in texts if not t.strip())
    }
    print("Embedding Statistics:", json.dumps(stats, indent=2))

def get_embedding_dim() -> Optional[int]:
    """Возвращает размерность эмбеддингов модели."""
    if model:
        try:
            # Предпочтительный способ для SentenceTransformer
            dim = model.get_sentence_embedding_dimension()
            if dim: return dim
        except Exception:
            pass

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