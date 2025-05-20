# --- START OF FILE search_engine.py (Refactored v3 - Added hybrid search) ---

import faiss
import numpy as np
import os
import json
import traceback
import sys
import re
from typing import List, Tuple, Dict, Any, Optional
from tqdm import tqdm

# --- Конфигурация Путей ---
CACHE_DIR = "data/cache"

# Имена файлов артефактов (должны совпадать с run_embedder.py)
EMBEDDINGS_FILENAME = "embeddings.npy"
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

def keyword_search(query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
    """
    Выполняет поиск по ключевым словам в тексте чанков.
    """
    if not is_initialized:
        if not _load_index_and_chunks():
            return []

    # Подготовка запроса
    query_terms = set(re.findall(r'\w+', query.lower()))
    if not query_terms:
        return []

    results_with_scores: List[Tuple[Dict[str, Any], float]] = []
    
    for chunk in indexed_chunks:
        text = chunk.get('text', '').lower()
        if not text:
            continue
            
        # Подсчет совпадений терминов
        matches = sum(1 for term in query_terms if term in text)
        if matches > 0:
            # Нормализованный скор: количество совпадений / количество терминов
            score = matches / len(query_terms)
            results_with_scores.append((chunk, score))

    # Сортировка по убыванию скора
    results_with_scores.sort(key=lambda x: x[1], reverse=True)
    return results_with_scores[:top_k]

def hybrid_search(query: str, query_vector: np.ndarray, top_k: int = 5, 
                 semantic_weight: float = 0.7) -> List[Tuple[Dict[str, Any], float]]:
    """
    Комбинированный поиск по эмбеддингам и ключевым словам.
    
    Args:
        query: Текстовый запрос
        query_vector: Вектор запроса для семантического поиска
        top_k: Количество возвращаемых результатов
        semantic_weight: Вес семантического поиска (0-1)
    """
    # Получаем результаты обоих типов поиска
    semantic_results = semantic_search(query_vector, top_k=top_k * 2)
    keyword_results = keyword_search(query, top_k=top_k * 2)
    
    # Создаем словарь для объединения результатов
    combined_results: Dict[str, Tuple[Dict[str, Any], float]] = {}
    
    # Обрабатываем семантические результаты
    for chunk, score in semantic_results:
        chunk_id = chunk.get('id', '')
        if chunk_id:
            combined_results[chunk_id] = (chunk, score * semantic_weight)
    
    # Объединяем с результатами поиска по ключевым словам
    for chunk, score in keyword_results:
        chunk_id = chunk.get('id', '')
        if chunk_id:
            if chunk_id in combined_results:
                # Если чанк уже есть, обновляем скор
                old_chunk, old_score = combined_results[chunk_id]
                combined_results[chunk_id] = (chunk, old_score + score * (1 - semantic_weight))
            else:
                # Добавляем новый результат
                combined_results[chunk_id] = (chunk, score * (1 - semantic_weight))
    
    # Сортируем по убыванию скора
    final_results = sorted(combined_results.values(), key=lambda x: x[1], reverse=True)
    return final_results[:top_k]

def filter_search_results(results: List[Tuple[Dict[str, Any], float]], 
                         filters: Dict[str, Any]) -> List[Tuple[Dict[str, Any], float]]:
    """
    Фильтрация результатов поиска по метаданным.
    
    Args:
        results: Список результатов поиска
        filters: Словарь с условиями фильтрации {поле: значение}
    """
    if not filters:
        return results
        
    filtered_results = []
    for chunk, score in results:
        # Проверяем все условия фильтра
        if all(chunk.get(k) == v for k, v in filters.items()):
            filtered_results.append((chunk, score))
            
    return filtered_results

def evaluate_search_quality(query: str, results: List[Tuple[Dict[str, Any], float]]) -> Dict[str, float]:
    """
    Оценка качества поиска.
    
    Args:
        query: Исходный запрос
        results: Результаты поиска
    """
    if not results:
        return {
            'relevance_score': 0.0,
            'diversity_score': 0.0,
            'coverage_score': 0.0
        }
    
    # Оценка релевантности (средний скор)
    relevance_score = sum(score for _, score in results) / len(results)
    
    # Оценка разнообразия (уникальные источники)
    sources = set(chunk.get('source', '') for chunk, _ in results)
    diversity_score = len(sources) / len(results)
    
    # Оценка покрытия (длина найденных чанков)
    total_length = sum(len(chunk.get('text', '')) for chunk, _ in results)
    coverage_score = min(1.0, total_length / 1000)  # Нормализуем по 1000 символов
    
    return {
        'relevance_score': float(relevance_score),
        'diversity_score': float(diversity_score),
        'coverage_score': float(coverage_score)
    }

def update_index(new_chunks: List[Dict[str, Any]], 
                new_embeddings: np.ndarray) -> bool:
    """
    Обновление индекса новыми данными.
    
    Args:
        new_chunks: Новые чанки для добавления
        new_embeddings: Эмбеддинги новых чанков
    """
    global faiss_index, indexed_chunks
    
    if not is_initialized:
        if not _load_index_and_chunks():
            return False
            
    try:
        # Проверяем размерность
        if new_embeddings.shape[1] != index_dimension:
            sys.stderr.write(f"❌ Ошибка: Размерность новых эмбеддингов ({new_embeddings.shape[1]}) "
                            f"не совпадает с размерностью индекса ({index_dimension}).\n")
            return False
            
        # Добавляем новые векторы в индекс
        if new_embeddings.flags['C_CONTIGUOUS']:
            faiss_index.add(new_embeddings.astype(np.float32))
        else:
            new_embeddings = np.ascontiguousarray(new_embeddings.astype(np.float32))
            faiss_index.add(new_embeddings)
        
        # Обновляем данные чанков
        indexed_chunks.extend(new_chunks)
        
        # Сохраняем обновленный индекс
        faiss.write_index(faiss_index, FAISS_INDEX_PATH)
        
        # Сохраняем обновленные данные чанков
        with open(INDEXED_CHUNKS_PATH, "w", encoding="utf-8") as f:
            json.dump(indexed_chunks, f, indent=2, ensure_ascii=False, default=str)
            
        print(f"✅ Индекс успешно обновлен. Добавлено {len(new_chunks)} новых чанков.")
        return True
        
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при обновлении индекса: {e}\n")
        traceback.print_exc()
        return False

# --- Функция для предварительной загрузки (можно вызвать при старте приложения) ---
def initialize_search_engine():
    """Выполняет загрузку индекса и данных чанков заранее."""
    _load_index_and_chunks()

# --- END OF FILE search_engine.py ---