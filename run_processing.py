# --- START OF FILE run_processing.py (Refactored v3) ---
import os
import sys
import traceback
from typing import List, Dict, Any

# Используем относительные импорты внутри пакета document_processor
try:
    from document_processor.document_parser import parse_document, RawContentBlock
    from document_processor.chunker import SimpleRecursiveTextSplitter
    from document_processor.metadata_extractor import extract_metadata
    from document_processor.common_utils import clean_text, hash_chunk, save_chunks_json, format_table_to_markdown
    print("✅ All modules imported successfully.")
except ImportError as e:
     sys.stderr.write(f"❌ Failed to import modules. Ensure they are in the correct path/package structure: {e}\n")
     sys.exit(1) # Выходим, если базовые модули не найдены

# --- Конфигурация (можно вынести в config.py или .env) ---
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
PROCESSED_JSON_FILENAME = "processed_chunks.json"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, PROCESSED_JSON_FILENAME)

# Настройки чанкера
CHUNK_SIZE = 800
CHUNK_OVERLAP = 200
SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""] # Добавил ; ,

# Инициализация сплиттера
text_splitter = SimpleRecursiveTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=SEPARATORS
)

def process_single_document(file_path: str) -> List[Dict[str, Any]]:
    """
    Обрабатывает один документ: парсит, чанкует, извлекает метаданные.
    Возвращает список готовых чанков для этого документа.
    """
    document_name = os.path.basename(file_path)
    processed_chunks: List[Dict[str, Any]] = []
    chunk_index_counter = 0 # Сквозной счетчик чанков для одного документа

    try:
        # 1. Парсинг документа -> Генератор RawContentBlock
        raw_content_generator = parse_document(file_path)

        # 2. Обработка каждого блока контента
        for block in raw_content_generator:
            block_chunks: List[str] = []
            block_text_representation: str = ""
            base_source_info = block.source_info # Общая инфа о блоке

            try:
                # --- Обработка текстовых блоков ---
                if block.type == 'text' and isinstance(block.content, str):
                    block_text_representation = block.content # Уже очищено в парсере
                    # Чанкуем текст блока
                    block_chunks = text_splitter.split_text(block_text_representation)

                # --- Обработка табличных блоков (PDF/DOCX) ---
                elif block.type == 'table' and isinstance(block.content, list):
                    table_data = block.content
                    headers = base_source_info.get("headers", [])
                    # Генерируем Markdown представление таблицы
                    block_text_representation = format_table_to_markdown(table_data, headers)
                    # Решаем, нужно ли чанковать Markdown таблицы
                    # Пока будем считать таблицу одним чанком, если она не слишком большая
                    if len(block_text_representation) <= CHUNK_SIZE * 1.5: # Коэфф. 1.5 для запаса
                         block_chunks = [block_text_representation]
                    else:
                         # Если таблица большая, чанкуем её Markdown представление как текст
                         # (Это может нарушить структуру, но лучше, чем огромный чанк)
                         print(f"    ⚠️ Table Markdown is large ({len(block_text_representation)} chars), chunking as text...")
                         block_chunks = text_splitter.split_text(block_text_representation)

                # --- Обработка строк Excel ---
                elif block.type == 'excel_row' and isinstance(block.content, dict):
                    row_data = block.content
                    # Формируем текстовое представление строки "ключ: значение. ключ2: значение2."
                    text_parts = [f"{k}: {v}" for k, v in row_data.items()]
                    block_text_representation = ". ".join(text_parts) + "." if text_parts else "Пустая строка Excel."
                    # Строку Excel обычно не чанкуем дополнительно, считаем её одним чанком
                    block_chunks = [block_text_representation]

                else:
                    sys.stderr.write(f"  ⚠️ Unknown block type '{block.type}' or invalid content in '{document_name}'. Skipping block.\n")
                    continue

                # --- Создание чанков с метаданными ---
                for chunk_text in block_chunks:
                    if not chunk_text or not chunk_text.strip():
                        continue # Пропускаем пустые чанки

                    chunk_id = hash_chunk(chunk_text, document_name, chunk_index_counter)

                    # --- Извлечение метаданных для чанка ---
                    # Передаем всю релевантную информацию
                    meta = extract_metadata(
                        chunk_text=chunk_text,
                        document_name=document_name,
                        source_type=f"{block.type}_chunk", # Уточняем тип источника
                        page_number=base_source_info.get("page_number"),
                        table_headers=base_source_info.get("headers") if block.type in ['table', 'excel_row'] else None,
                        table_data=block.content if block.type == 'table' else None,
                        excel_row_data=block.content if block.type == 'excel_row' else None,
                        document_hyperlinks=base_source_info.get("document_hyperlinks"),
                        current_heading=base_source_info.get("current_heading")
                    )
                    # Добавляем ID чанка и документа в мету для удобства
                    meta["chunk_id"] = chunk_id
                    meta["chunk_index_in_doc"] = chunk_index_counter

                    processed_chunks.append({
                        "id": chunk_id,
                        "text": chunk_text.strip(),
                        "meta": meta
                    })
                    chunk_index_counter += 1

            except Exception as e_block:
                 sys.stderr.write(f"  ❌ ERROR processing block ({block.type}) in '{document_name}': {e_block}\n")
                 traceback.print_exc(limit=1) # Краткий трейсбек для ошибки блока

    except Exception as e_doc:
        sys.stderr.write(f"❌❌ CRITICAL ERROR processing document '{document_name}': {e_doc}\n")
        traceback.print_exc() # Полный трейсбек для критической ошибки документа
        return [] # Возвращаем пустой список для этого документа

    print(f"✅ Finished processing: {document_name}. Total chunks generated: {len(processed_chunks)}")
    return processed_chunks


def main():
    """
    Основная функция для запуска обработки всех документов в INPUT_DIR.
    """
    all_processed_chunks: List[Dict[str, Any]] = []
    processed_files_count = 0
    skipped_files_count = 0

    # Создаем директорию вывода, если её нет
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("-" * 60)
    print(f"🚀 Starting document processing from directory: {INPUT_DIR}")
    print(f"➡️ Output will be saved to: {OUTPUT_PATH}")
    print(f"⚙️ Chunk settings: size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
    print("-" * 60)

    if not os.path.exists(INPUT_DIR):
        print(f"❌ Error: Input directory '{INPUT_DIR}' not found.")
        return

    try:
        files_to_process = [f for f in os.listdir(INPUT_DIR) if os.path.isfile(os.path.join(INPUT_DIR, f))]
    except FileNotFoundError:
        print(f"❌ Error: Cannot access input directory '{INPUT_DIR}'.")
        return

    if not files_to_process:
        print(f"ℹ️ No files found in '{INPUT_DIR}' to process.")
        return

    # Обрабатываем каждый файл
    for filename in files_to_process:
        # Пропускаем временные файлы (например, от MS Office)
        if filename.startswith('~$') or filename.startswith('.'):
            print(f"\nℹ️ Skipping temporary/hidden file: {filename}")
            skipped_files_count += 1
            continue

        file_path = os.path.join(INPUT_DIR, filename)
        print(f"\n--- Processing file: {filename} ---")

        try:
            # Вызываем функцию обработки одного документа
            document_chunks = process_single_document(file_path)

            if document_chunks:
                all_processed_chunks.extend(document_chunks)
                processed_files_count += 1
            elif document_chunks == []: # Если функция вернула пустой список (были ошибки или файл пуст/неподдерживаемый)
                 print(f"ℹ️ No chunks generated for '{filename}'. It might be unsupported, empty, or processing failed.")
                 skipped_files_count += 1
            # Случай None не должен возникать, но на всякий случай
            else:
                print(f"⚠️ Unexpected empty result for '{filename}'. Skipping.")
                skipped_files_count += 1

        except Exception as e:
            # Отлов неожиданных ошибок на уровне файла (хотя process_single_document должна их ловить)
            print(f"❌❌ UNHANDLED CRITICAL ERROR during processing of '{filename}': {e}")
            traceback.print_exc()
            skipped_files_count += 1
        print(f"--- Finished file: {filename} ---")

    # --- Сохранение результатов ---
    print("\n" + "=" * 60)
    print("📊 Processing Summary:")
    print(f"  Processed files: {processed_files_count}")
    print(f"  Skipped/Failed files: {skipped_files_count}")
    print(f"  Total chunks generated: {len(all_processed_chunks)}")
    print("=" * 60)

    if all_processed_chunks:
        print(f"💾 Saving all {len(all_processed_chunks)} chunks to {OUTPUT_PATH}...")
        save_chunks_json(all_processed_chunks, OUTPUT_PATH)
    else:
        print("\nℹ️ No chunks were generated to save.")

    print("\n🎉 Document processing finished.")


if __name__ == "__main__":
    # Устанавливаем кодировку stdout/stderr в UTF-8 (полезно в Windows)
    # sys.stdout.reconfigure(encoding='utf-8')
    # sys.stderr.reconfigure(encoding='utf-8')
    main()
# --- END OF FILE run_processing.py ---