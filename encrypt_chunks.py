# encrypt_chunks.py — утилита для шифровки processed_chunks.json

import json
from encryptor_tools import obfuscate_text, save_map
from pathlib import Path

IN_FILE = "data/output/processed_chunks.json"
OUT_FILE = "data/output/processed_chunks_obfuscated.json"
MAP_FILE = "data/output/obfuscation_map.json"

mask_map = {}

with open(IN_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

new_chunks = []
for chunk in chunks:
    new_chunk = dict(chunk)
    if "text" in chunk:
        new_chunk["text"] = obfuscate_text(chunk["text"], mask_map)
    new_chunks.append(new_chunk)

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(new_chunks, f, ensure_ascii=False, indent=2)

save_map(mask_map, MAP_FILE)

print(f"✅ Зашифровано: {len(new_chunks)} чанков")
print(f"💾 Сохранено в: {OUT_FILE}")
