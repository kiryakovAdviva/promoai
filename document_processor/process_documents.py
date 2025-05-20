import os
import json
from typing import List, Dict, Any
from document_processor.chunker import SemanticDocumentChunker
from document_processor.document_parser import parse_document
from document_processor.metadata_extractor import extract_metadata

INPUT_DIR = "data/input"
OUTPUT_PATH = "data/output/processed_chunks.json"
EXCEL_CONTACTS = "data/input/Promo_Contact_information.xlsx"

def process_document(file_path: str) -> List[Dict[str, Any]]:
    """Обрабатывает один документ и возвращает список чанков с метаданными."""
    print(f"📄 Обрабатываем файл: {os.path.basename(file_path)}")
    
    # Инициализируем чанкер
    chunker = SemanticDocumentChunker(
        min_chunk_size=100,
        max_chunk_size=1000,
        overlap_size=100
    )
    
    # Парсим документ
    raw_content = parse_document(file_path)
    
    # Обрабатываем каждый блок контента
    all_chunks = []
    for block in raw_content:
        if block.type == 'text':
            # Разбиваем текст на семантические чанки
            chunks = chunker.split_document(block.content)
            all_chunks.extend(chunks)
        elif block.type == 'table':
            # Для таблиц создаем один чанк с метаданными
            table_text = '\n'.join([' | '.join(row) for row in block.content])
            chunks = chunker.split_document(table_text)
            for chunk in chunks:
                chunk['metadata']['chunk_type'] = 'table'
                chunk['metadata']['table_headers'] = block.source_info.get('headers', [])
            all_chunks.extend(chunks)
    
    return all_chunks

def extract_contacts_as_chunks(excel_path: str) -> List[Dict[str, Any]]:
    """Извлекает контакты из Excel и создает для них чанки."""
    # TODO: Реализовать извлечение контактов из Excel
    return []

def main():
    all_chunks = []

    # Обрабатываем документы
    for filename in os.listdir(INPUT_DIR):
        if filename.endswith((".pdf", ".docx")):
            path = os.path.join(INPUT_DIR, filename)
            chunks = process_document(path)
            print(f"✅ Чанков: {len(chunks)}")
            all_chunks.extend(chunks)

    # Обрабатываем Excel с контактами
    if os.path.exists(EXCEL_CONTACTS):
        print("👥 Обрабатываем Excel с контактами...")
        contact_chunks = extract_contacts_as_chunks(EXCEL_CONTACTS)
        print(f"➕ Добавлено контактных чанков: {len(contact_chunks)}")
        all_chunks.extend(contact_chunks)

    # Сохраняем результаты
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"💾 Готово. Всего чанков: {len(all_chunks)} → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
