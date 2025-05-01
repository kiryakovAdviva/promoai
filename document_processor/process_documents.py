
import os
import json
from document_processor.utils import process_document, extract_contacts_as_chunks

INPUT_DIR = "data/input"
OUTPUT_PATH = "data/output/processed_chunks.json"
EXCEL_CONTACTS = "data/input/Promo_Contact_information.xlsx"

def main():
    all_chunks = []

    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".pdf") or filename.endswith(".docx"):
            path = os.path.join(INPUT_DIR, filename)
            print(f"📄 Обрабатываем файл: {filename}")
            chunks = process_document(path)
            print(f"✅ Чанков: {len(chunks)}")
            all_chunks.extend(chunks)

    if os.path.exists(EXCEL_CONTACTS):
        print("👥 Обрабатываем Excel с контактами...")
        contact_chunks = extract_contacts_as_chunks(EXCEL_CONTACTS)
        print(f"➕ Добавлено контактных чанков: {len(contact_chunks)}")
        all_chunks.extend(contact_chunks)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"💾 Готово. Всего чанков: {len(all_chunks)} → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
