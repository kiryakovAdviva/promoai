# --- START OF FILE run_embedder.py (Refactored v3 - Исправлен вывод имени модели) ---

import os
import json
import numpy as np
import faiss
import sys
import traceback

# --- Импорты из нашего проекта ---
try:
    # Используем относительные импорты, если структура пакета
    # from assistant.embedder import model, embed_texts, get_embedding_dim, MODEL_NAME # Добавил MODEL_NAME
    # from document_processor.common_utils import load_chunks_json
    # Если запускаем как скрипт, пробуем прямые импорты
    from assistant.embedder import model, embed_texts, get_embedding_dim, MODEL_NAME # Добавил MODEL_NAME
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
PROCESSED_CHUNKS_FILENAME = "processed_chunks.json"
CHUNKS_PATH = os.path.join(OUTPUT_DIR, PROCESSED_CHUNKS_FILENAME)
CACHE_DIR = "data/cache"
EMBEDDINGS_FILENAME = "embeddings.npy"
INDEXED_CHUNKS_FILENAME = "indexed_chunks.json"
FAISS_INDEX_FILENAME = "faiss_index.bin"
EMBEDDINGS_PATH = os.path.join(CACHE_DIR, EMBEDDINGS_FILENAME)
INDEXED_CHUNKS_PATH = os.path.join(CACHE_DIR, INDEXED_CHUNKS_FILENAME)
FAISS_INDEX_PATH = os.path.join(CACHE_DIR, FAISS_INDEX_FILENAME)

def run_embedding_pipeline():
    """
    Запускает полный процесс создания эмбеддингов и FAISS-индекса.
    """
    print("-" * 60)
    print("🚀 Запуск процесса создания эмбеддингов и FAISS индекса...")
    print(f"📂 Исходные чанки: {CHUNKS_PATH}")
    print(f"💾 Артефакты будут сохранены в: {CACHE_DIR}")
    print("-" * 60)

    if model is None:
        sys.stderr.write("❌ КРИТИЧЕСКАЯ ОШИБКА: Модель эмбеддингов не была загружена в embedder.py. Прерывание.\n")
        sys.exit(1)

    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        print(f"✅ Директория кэша '{CACHE_DIR}' проверена/создана.")
    except OSError as e:
        sys.stderr.write(f"❌ Ошибка при создании директории кэша '{CACHE_DIR}': {e}\n")
        sys.exit(1)

    print(f"📖 Загрузка обработанных чанков из {CHUNKS_PATH}...")
    chunks = load_chunks_json(CHUNKS_PATH)
    if not chunks:
        print(f"⚠️ Предупреждение: Файл '{CHUNKS_PATH}' пуст или не найден. Нет данных для эмбеддинга.")
        return

    print(f"📊 Загружено чанков: {len(chunks)}")

    texts_to_embed = [chunk.get("text", "") for chunk in chunks]
    valid_indices = [i for i, text in enumerate(texts_to_embed) if text and text.strip()]
    if len(valid_indices) != len(texts_to_embed):
        print(f"⚠️ Предупреждение: Обнаружено {len(texts_to_embed) - len(valid_indices)} пустых чанков. Они будут пропущены при эмбеддинге.")
        valid_chunks = [chunks[i] for i in valid_indices]
        valid_texts = [texts_to_embed[i] for i in valid_indices]
        if not valid_chunks:
            print("⚠️ Предупреждение: Не осталось валидных непустых чанков для эмбеддинга.")
            return
        chunks = valid_chunks
        texts_to_embed = valid_texts
        print(f"📊 Осталось валидных чанков для эмбеддинга: {len(chunks)}")

    # --- ИСПРАВЛЕНИЕ: Используем MODEL_NAME для вывода ---
    print(f"🧠 Генерация эмбеддингов для {len(texts_to_embed)} чанков (Модель: {MODEL_NAME})...")
    # --- Конец исправления ---
    embeddings = embed_texts(texts_to_embed)

    if embeddings is None or embeddings.size == 0:
        sys.stderr.write("❌ Ошибка: Не удалось сгенерировать эмбеддинги.\n")
        return

    print(f"🔢 Размерность эмбеддингов: {embeddings.shape[1]}")
    print(f"🔢 Количество эмбеддингов: {embeddings.shape[0]}")

    try:
        print(f"💾 Сохранение эмбеддингов в {EMBEDDINGS_PATH}...")
        np.save(EMBEDDINGS_PATH, embeddings.astype(np.float32))

        print(f"💾 Сохранение соответствующих чанков в {INDEXED_CHUNKS_PATH}...")
        with open(INDEXED_CHUNKS_PATH, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False, default=str)
        print("✅ Эмбеддинги и чанки сохранены.")
    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при сохранении эмбеддингов или чанков: {e}\n")
        traceback.print_exc()
        return

    embedding_dim = embeddings.shape[1]
    model_dim = get_embedding_dim()
    if model_dim is not None and embedding_dim != model_dim:
         print(f"⚠️ Предупреждение: Размерность сгенерированных эмбеддингов ({embedding_dim}) не совпадает с ожидаемой размерностью модели ({model_dim}).")

    print(f"🛠️ Создание FAISS индекса (IndexFlatIP) с размерностью {embedding_dim}...")
    try:
        index = faiss.IndexFlatIP(embedding_dim)
        # Добавляем проверки перед добавлением векторов
        if embeddings.flags['C_CONTIGUOUS']:
             index.add(embeddings.astype(np.float32))
        else:
             print("⚠️ Предупреждение: Массив эмбеддингов не C-contiguous. Создается копия.")
             embeddings_contiguous = np.ascontiguousarray(embeddings.astype(np.float32))
             index.add(embeddings_contiguous)

        print(f"📊 FAISS индекс создан. Количество векторов в индексе: {index.ntotal}")

        print(f"💾 Сохранение FAISS индекса в {FAISS_INDEX_PATH}...")
        faiss.write_index(index, FAISS_INDEX_PATH)
        print("✅ FAISS индекс успешно сохранен.")

    except Exception as e:
        sys.stderr.write(f"❌ Ошибка при создании или сохранении FAISS индекса: {e}\n")
        traceback.print_exc()
        return

    print("-" * 60)
    print("🎉 Процесс создания эмбеддингов и индекса завершен успешно!")
    print(f"   - Эмбеддинги: {EMBEDDINGS_PATH}")
    print(f"   - Данные чанков: {INDEXED_CHUNKS_PATH}")
    print(f"   - FAISS Индекс: {FAISS_INDEX_PATH}")
    print("-" * 60)

if __name__ == "__main__":
    run_embedding_pipeline()

# --- END OF FILE run_embedder.py ---