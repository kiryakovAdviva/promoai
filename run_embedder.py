# --- START OF FILE run_embedder.py (Refactored v5 - Added progress bars) ---

import os
import json
import numpy as np
import faiss
import sys
import traceback
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import time

# --- Импорты из нашего проекта ---
try:
    # Используем относительные импорты, если структура пакета
    # from assistant.embedder import model, embed_texts, get_embedding_dim, MODEL_NAME # Добавил MODEL_NAME
    # from document_processor.common_utils import load_chunks_json
    # Если запускаем как скрипт, пробуем прямые импорты
    from assistant.embedder import (
        model, embed_texts_batched, get_embedding_dim, MODEL_NAME,
        validate_embeddings, log_embedding_stats
    )
    from document_processor.common_utils import load_chunks_json
    print("✅ Импорты embedder и common_utils выполнены.")
except ImportError as e:
    sys.stderr.write(f"❌ Ошибка импорта необходимых модулей: {e}\n")
    sys.stderr.write("   Убедитесь, что embedder.py и папка document_processor находятся в PYTHONPATH или запускаются как часть пакета.\n")
    sys.exit(1)
except Exception as e_imp: # Ловим другие возможные ошибки импорта (например, NameError, если MODEL_NAME не определен в embedder.py)
    sys.stderr.write(f"❌ Ошибка при импорте: {e_imp}\n")
    sys.exit(1)


# --- Конфигурация Путей ---
OUTPUT_DIR = os.path.join("data", "output")
PROCESSED_CHUNKS_FILENAME = "processed_chunks_obfuscated.json"
CHUNKS_PATH = os.path.join(OUTPUT_DIR, PROCESSED_CHUNKS_FILENAME)
CACHE_DIR = "data/cache"
EMBEDDINGS_FILENAME = "embeddings.npy"
INDEXED_CHUNKS_FILENAME = "indexed_chunks.json"
FAISS_INDEX_FILENAME = "faiss_index.bin"
EMBEDDINGS_PATH = os.path.join(CACHE_DIR, EMBEDDINGS_FILENAME)
INDEXED_CHUNKS_PATH = os.path.join(CACHE_DIR, INDEXED_CHUNKS_FILENAME)
FAISS_INDEX_PATH = os.path.join(CACHE_DIR, FAISS_INDEX_FILENAME)

def create_optimized_index(dimension: int, num_vectors: int) -> faiss.Index:
    """Создание оптимизированного индекса FAISS"""
    if num_vectors > 1000000:
        # Для больших наборов данных используем IVF
        nlist = min(int(np.sqrt(num_vectors)), 1000)
        quantizer = faiss.IndexFlatIP(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
        print(f"✅ Создан IVF индекс с {nlist} кластерами")
    else:
        # Для небольших наборов используем HNSW
        index = faiss.IndexHNSWFlat(dimension, 32)  # 32 - количество соседей
        print("✅ Создан HNSW индекс")
    return index

def cache_embeddings(embeddings: np.ndarray, cache_path: str):
    """Сохранение промежуточных результатов"""
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        np.save(cache_path, embeddings)
        print(f"✅ Эмбеддинги сохранены в кэш: {cache_path}")
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при сохранении эмбеддингов в кэш: {e}\n")

def run_embedding_pipeline():
    """
    Запускает полный процесс создания эмбеддингов и FAISS-индекса.
    """
    print("\n" + "=" * 60)
    print("🚀 Запуск процесса создания эмбеддингов и FAISS индекса...")
    print(f"📂 Исходные чанки: {CHUNKS_PATH}")
    print(f"💾 Артефакты будут сохранены в: {CACHE_DIR}")
    print("=" * 60 + "\n")

    if model is None:
        sys.stderr.write("❌ КРИТИЧЕСКАЯ ОШИБКА: Модель эмбеддингов не была загружена в embedder.py. Прерывание.\n")
        sys.exit(1)

    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        print(f"✅ Директория кэша '{CACHE_DIR}' проверена/создана.")
    except OSError as e:
        sys.stderr.write(f"❌ Ошибка при создании директории кэша '{CACHE_DIR}': {e}\n")
        sys.exit(1)

    # Загрузка чанков с прогресс-баром
    print(f"📖 Загрузка обработанных чанков из {CHUNKS_PATH}...")
    chunks = load_chunks_json(CHUNKS_PATH)
    if not chunks:
        print(f"⚠️ Предупреждение: Файл '{CHUNKS_PATH}' пуст или не найден. Нет данных для эмбеддинга.")
        return

    print(f"📊 Загружено чанков: {len(chunks)}")

    # Подготовка текстов с прогресс-баром
    print("\n🔄 Подготовка текстов для эмбеддингов...")
    texts_to_embed = []
    valid_indices = []
    
    with tqdm(total=len(chunks), desc="Подготовка текстов", unit="чанк") as pbar:
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            if text and text.strip():
                texts_to_embed.append(text)
                valid_indices.append(i)
            pbar.update(1)

    if len(valid_indices) != len(chunks):
        print(f"⚠️ Предупреждение: Обнаружено {len(chunks) - len(valid_indices)} пустых чанков. Они будут пропущены при эмбеддинге.")
        valid_chunks = [chunks[i] for i in valid_indices]
        if not valid_chunks:
            print("⚠️ Предупреждение: Не осталось валидных непустых чанков для эмбеддинга.")
            return
        chunks = valid_chunks  # Обновляем список чанков только валидными
        print(f"📊 Осталось валидных чанков для эмбеддинга: {len(chunks)}")

    # Генерация эмбеддингов с прогресс-баром
    print(f"\n🧠 Генерация эмбеддингов для {len(texts_to_embed)} чанков (Модель: {MODEL_NAME})...")
    start_time = time.time()
    embeddings = embed_texts_batched(texts_to_embed, batch_size=32)
    end_time = time.time()
    
    if embeddings is None or embeddings.size == 0:
        sys.stderr.write("❌ Ошибка: Не удалось сгенерировать эмбеддинги.\n")
        return

    print(f"\n✅ Генерация эмбеддингов завершена за {end_time - start_time:.2f} секунд")
    print(f"🔢 Размерность эмбеддингов: {embeddings.shape[1]}")
    print(f"🔢 Количество эмбеддингов: {embeddings.shape[0]}")

    # Проверка соответствия количества чанков и эмбеддингов
    if len(chunks) != embeddings.shape[0]:
        print(f"❌ Ошибка: Несоответствие количества чанков ({len(chunks)}) и эмбеддингов ({embeddings.shape[0]})")
        return

    # Сохранение результатов с прогресс-баром
    print("\n💾 Сохранение результатов...")
    try:
        with tqdm(total=2, desc="Сохранение", unit="файл") as pbar:
            print(f"  Сохранение эмбеддингов в {EMBEDDINGS_PATH}...")
            cache_embeddings(embeddings, EMBEDDINGS_PATH)
            pbar.update(1)

            print(f"  Сохранение чанков в {INDEXED_CHUNKS_PATH}...")
            with open(INDEXED_CHUNKS_PATH, "w", encoding="utf-8") as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False, default=str)
            pbar.update(1)
        print("✅ Эмбеддинги и чанки сохранены.")
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при сохранении эмбеддингов или чанков: {e}\n")
        traceback.print_exc()
        return

    embedding_dim = embeddings.shape[1]
    model_dim = get_embedding_dim()
    if model_dim is not None and embedding_dim != model_dim:
        print(f"⚠️ Предупреждение: Размерность сгенерированных эмбеддингов ({embedding_dim}) не совпадает с ожидаемой размерностью модели ({model_dim}).")

    # Создание и обучение индекса с прогресс-баром
    print(f"\n🛠️ Создание FAISS индекса с размерностью {embedding_dim}...")
    try:
        # Создаем оптимизированный индекс
        index = create_optimized_index(embedding_dim, len(embeddings))
        
        # Добавляем векторы в индекс с прогресс-баром
        print("  Добавление векторов в индекс...")
        with tqdm(total=1, desc="Индексация", unit="операция") as pbar:
            if embeddings.flags['C_CONTIGUOUS']:
                index.add(embeddings.astype(np.float32))
            else:
                print("⚠️ Предупреждение: Массив эмбеддингов не C-contiguous. Создается копия.")
                embeddings_contiguous = np.ascontiguousarray(embeddings.astype(np.float32))
                index.add(embeddings_contiguous)
            pbar.update(1)

        print(f"📊 FAISS индекс создан. Количество векторов в индексе: {index.ntotal}")

        # Сохранение индекса с прогресс-баром
        print(f"\n💾 Сохранение FAISS индекса в {FAISS_INDEX_PATH}...")
        with tqdm(total=1, desc="Сохранение индекса", unit="операция") as pbar:
            faiss.write_index(index, FAISS_INDEX_PATH)
            pbar.update(1)
        print("✅ FAISS индекс успешно сохранен.")

    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при создании или сохранении FAISS индекса: {e}\n")
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("🎉 Процесс создания эмбеддингов и индекса завершен успешно!")
    print(f"   - Эмбеддинги: {EMBEDDINGS_PATH}")
    print(f"   - Данные чанков: {INDEXED_CHUNKS_PATH}")
    print(f"   - FAISS Индекс: {FAISS_INDEX_PATH}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    run_embedding_pipeline()

# --- END OF FILE run_embedder.py ---