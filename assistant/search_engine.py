# --- START OF FILE search_engine.py (Refactored v2) ---

import faiss
import numpy as np
import os
import json
import traceback
import sys
from typing import List, Tuple, Dict, Any, Optional

# --- Конфигурация Путей ---
CACHE_DIR = "data/cache"

# Имена файлов артефактов (должны совпадать с run_embedder.py)
EMBEDDINGS_FILENAME = "embeddings.npy" # Хотя сами эмбеддинги не нужны для поиска с FAISS
INDEXED_CHUNKS_FILENAME = "indexed_chunks.json"
FAISS_INDEX_FILENAME = "faiss_index.bin"

INDEXED_CHUNKS_PATH = os.path.join(CACHE_DIR, INDEXED_CHUNKS_FILENAME)
FAISS_INDEX_PATH = os.path.join(CACHE_DIR, FAISS_INDEX_FILENAME)

# --- Глобальные переменные для кэширования индекса и данных ---
faiss_index: Optional[faiss.Index] = None
indexed_chunks: List[Dict[str, Any]] = []
index_dimension: Optional[int] = None
is_initialized: bool = False

def _load_index_and_chunks() -> bool:
    """Загружает FAISS индекс и соответствующие данные чанков."""
    global faiss_index, indexed_chunks, index_dimension, is_initialized

    if is_initialized: # Уже загружено
        return True

    print("🔄 Инициализация поискового движка: Загрузка FAISS индекса и данных чанков...")

    # --- Проверка наличия файлов ---
    if not os.path.exists(FAISS_INDEX_PATH):
        sys.stderr.write(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Файл FAISS индекса не найден по пути: {FAISS_INDEX_PATH}\n")
        sys.stderr.write("   Запустите скрипт run_embedder.py для его создания.\n")
        return False
    if not os.path.exists(INDEXED_CHUNKS_PATH):
        sys.stderr.write(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Файл данных индексированных чанков не найден по пути: {INDEXED_CHUNKS_PATH}\n")
        sys.stderr.write("   Запустите скрипт run_embedder.py для его создания.\n")
        return False

    # --- Загрузка ---
    try:
        print(f"   Загрузка FAISS индекса из {FAISS_INDEX_PATH}...")
        faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        index_dimension = faiss_index.d
        print(f"   ✅ FAISS индекс загружен (Размерность: {index_dimension}, Кол-во векторов: {faiss_index.ntotal}).")

        print(f"   Загрузка данных чанков из {INDEXED_CHUNKS_PATH}...")
        with open(INDEXED_CHUNKS_PATH, "r", encoding="utf-8") as f:
            indexed_chunks = json.load(f)
        print(f"   ✅ Данные чанков загружены (Кол-во: {len(indexed_chunks)}).")

        # --- Валидация ---
        if faiss_index.ntotal != len(indexed_chunks):
            sys.stderr.write("❌ КРИТИЧЕСКАЯ ОШИБКА: Несовпадение количества векторов в FAISS индексе "
                             f"({faiss_index.ntotal}) и количества загруженных чанков ({len(indexed_chunks)}).\n")
            sys.stderr.write("   Возможно, индекс или файл чанков устарели. Пересоздайте их (run_embedder.py).\n")
            # Сбрасываем состояние, чтобы предотвратить поиск
            faiss_index = None
            indexed_chunks = []
            index_dimension = None
            return False

        is_initialized = True
        print("✅ Поисковый движок успешно инициализирован.")
        return True

    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при загрузке/валидации индекса или данных чанков: {e}\n")
        traceback.print_exc()
        faiss_index = None
        indexed_chunks = []
        index_dimension = None
        return False

def semantic_search(query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
    """
    Выполняет семантический поиск по предзагруженному индексу.

    Args:
        query_vector (np.ndarray): Вектор запроса (уже нормализованный).
        top_k (int): Количество возвращаемых результатов.

    Returns:
        list: Список кортежей [(chunk_dict, similarity_score), ...], отсортированных по убыванию схожести.
              Или пустой список в случае ошибки.
    """
    global faiss_index, indexed_chunks, index_dimension, is_initialized

    # --- Инициализация при первом вызове ---
    if not is_initialized:
        if not _load_index_and_chunks():
            # Если инициализация не удалась, поиск невозможен
            return []

    # --- Проверка входных данных ---
    if faiss_index is None or index_dimension is None: # Дополнительная проверка
        sys.stderr.write("❌ Ошибка поиска: FAISS индекс не инициализирован.\n")
        return []
    if query_vector is None or query_vector.size == 0:
        sys.stderr.write("❌ Ошибка поиска: Получен пустой вектор запроса.\n")
        return []

    # --- Подготовка вектора запроса ---
    try:
        # FAISS ожидает float32
        query_vector_f32 = query_vector.astype(np.float32)
        # FAISS ожидает 2D массив (batch_size, dim)
        if query_vector_f32.ndim == 1:
            query_vector_f32 = np.expand_dims(query_vector_f32, axis=0)

        # Проверка размерности
        query_dim = query_vector_f32.shape[1]
        if query_dim != index_dimension:
            sys.stderr.write(f"❌ Ошибка: Размерность вектора запроса ({query_dim}) "
                             f"не совпадает с размерностью индекса ({index_dimension}).\n")
            return []
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при подготовке вектора запроса для FAISS: {e}\n")
        traceback.print_exc()
        return []

    # --- Выполнение поиска ---
    results_with_scores: List[Tuple[Dict[str, Any], float]] = []
    try:
        # print(f"🔍 Поиск FAISS top_k={top_k}...") # Отладочный вывод
        # index.search возвращает схожести (scores) и индексы (indices)
        scores, indices = faiss_index.search(query_vector_f32, top_k)
        # print(f"📊 Результаты FAISS raw: indices={indices}, scores={scores}") # Отладочный вывод

        # scores[0] и indices[0], так как у нас batch_size=1
        if len(indices) > 0 and len(scores) > 0:
            for rank, (idx, score) in enumerate(zip(indices[0], scores[0])):
                if idx == -1: # FAISS возвращает -1, если найдено меньше k
                    break
                if 0 <= idx < len(indexed_chunks):
                    results_with_scores.append((indexed_chunks[idx], float(score)))
                else:
                    # Эта ошибка не должна возникать при корректной связке индекса и данных
                    sys.stderr.write(f"⚠️ Предупреждение: Получен невалидный индекс ({idx}) от FAISS "
                                     f"(ранг {rank+1}). Макс. индекс в данных: {len(indexed_chunks)-1}.\n")
        # print(f"✅ Найдено результатов: {len(results_with_scores)}") # Отладочный вывод

    except Exception as e:
         sys.stderr.write(f"❌ Ошибка во время выполнения FAISS поиска: {e}\n")
         traceback.print_exc()
         return [] # Возвращаем пустой список при ошибке

    # IndexFlatIP возвращает скалярное произведение. Для нормализованных векторов
    # это эквивалентно косинусному сходству. FAISS сортирует по убыванию.
    return results_with_scores

# --- Функция для предварительной загрузки (можно вызвать при старте приложения) ---
def initialize_search_engine():
    """Выполняет загрузку индекса и данных чанков заранее."""
    _load_index_and_chunks()

# --- END OF FILE search_engine.py ---