# encrypt_chunks.py — утилита для шифровки processed_chunks.json

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from encryptor_tools import obfuscate_text, save_map, load_map

# Конфигурация путей
IN_FILE = "data/output/processed_chunks.json"
OUT_FILE = "data/output/processed_chunks_obfuscated.json"
MAP_FILE = "data/output/obfuscation_map.json"
BACKUP_DIR = "data/backup"

def backup_file(file_path: str) -> bool:
    """Создание резервной копии файла"""
    try:
        if not os.path.exists(file_path):
            return False
            
        backup_path = os.path.join(BACKUP_DIR, os.path.basename(file_path))
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        with open(file_path, 'r', encoding='utf-8') as src:
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании резервной копии: {e}")
        return False

def validate_chunks(chunks: List[Dict[str, Any]]) -> bool:
    """Валидация структуры чанков"""
    if not isinstance(chunks, list):
        print("❌ Ошибка: Чанки должны быть списком")
        return False
        
    required_fields = {"text", "metadata"}
    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            print(f"❌ Ошибка: Чанк {i} должен быть словарем")
            return False
            
        if not all(field in chunk for field in required_fields):
            print(f"❌ Ошибка: Чанк {i} не содержит все необходимые поля")
            return False
            
    return True

def process_chunks(chunks: List[Dict[str, Any]], mask_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Обработка чанков с обфускацией"""
    new_chunks = []
    for chunk in chunks:
        new_chunk = dict(chunk)
        
        # Обфускация текста
        if "text" in chunk:
            new_chunk["text"] = obfuscate_text(chunk["text"], mask_map)
            
        # Обфускация метаданных
        if "metadata" in chunk:
            metadata = chunk["metadata"]
            if isinstance(metadata, dict):
                for key, value in metadata.items():
                    if isinstance(value, str):
                        metadata[key] = obfuscate_text(value, mask_map)
                        
        new_chunks.append(new_chunk)
    return new_chunks

def main():
    """Основная функция обработки чанков"""
    print("\n🔐 Запуск процесса обфускации чанков...")
    
    # Проверка входного файла
    if not os.path.exists(IN_FILE):
        print(f"❌ Ошибка: Входной файл {IN_FILE} не найден")
        return
        
    # Создание резервной копии
    print("📦 Создание резервной копии...")
    if backup_file(IN_FILE):
        print("✅ Резервная копия создана")
    else:
        print("⚠️ Не удалось создать резервную копию")
        
    # Загрузка чанков
    print(f"\n📖 Загрузка чанков из {IN_FILE}...")
    try:
        with open(IN_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка при загрузке чанков: {e}")
        return
        
    # Валидация чанков
    if not validate_chunks(chunks):
        print("❌ Ошибка валидации чанков")
        return
        
    print(f"✅ Загружено {len(chunks)} чанков")
    
    # Обфускация
    print("\n🔄 Обфускация чанков...")
    mask_map = {}
    new_chunks = process_chunks(chunks, mask_map)
    
    # Сохранение результатов
    print("\n💾 Сохранение результатов...")
    try:
        # Сохранение обфусцированных чанков
        os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(new_chunks, f, ensure_ascii=False, indent=2)
            
        # Сохранение карты обфускации
        if not save_map(mask_map, MAP_FILE):
            print("❌ Ошибка при сохранении карты обфускации")
            return
            
        print(f"✅ Обфусцированные чанки сохранены в {OUT_FILE}")
        print(f"✅ Карта обфускации сохранена в {MAP_FILE}")
        
    except Exception as e:
        print(f"❌ Ошибка при сохранении результатов: {e}")
        return
        
    print(f"\n✅ Обработка завершена успешно!")
    print(f"📊 Статистика:")
    print(f"   - Обработано чанков: {len(chunks)}")
    print(f"   - Создано токенов: {len(mask_map)}")

if __name__ == "__main__":
    main()
