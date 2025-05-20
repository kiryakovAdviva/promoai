# --- START OF FILE common_utils.py ---
import re
import json
import hashlib
import os
from datetime import datetime
import numpy as np
import sys
from typing import Any, Dict, List, Optional

def clean_text(text: str) -> str:
    """Очищает текст от лишних пробелов и переносов строк."""
    if not text:
        return ""
    # Заменяем множественные пробелы и переносы строк
    text = ' '.join(text.split())
    return text.strip()

def hash_chunk(text: str, document_name: str, chunk_index: int) -> str:
    """Создает уникальный хеш для чанка."""
    content = f"{document_name}:{chunk_index}:{text}"
    return hashlib.md5(content.encode()).hexdigest()

def serialize_meta(obj: Any) -> Any:
    """Сериализует специальные типы для JSON (datetime, numpy)."""
    if isinstance(obj, datetime): return obj.isoformat()
    # Numpy types
    if isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)): return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)): return float(obj) if not np.isnan(obj) else None # Convert NaN to None
    elif isinstance(obj, (np.ndarray,)): return obj.tolist()
    elif isinstance(obj, (np.bool_)): return bool(obj)
    elif isinstance(obj, (np.void)): return None # Handle numpy void type
    # Fallback: try converting to string, useful for complex objects that might have a __str__ method
    try:
        return str(obj)
    except Exception:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable and has no default string representation")

def save_chunks_json(chunks: List[Dict[str, Any]], output_path: str) -> None:
    """Сохраняет чанки в JSON файл."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

def load_chunks_json(json_path: str) -> List[Dict]:
    """Загружает чанки из JSON файла."""
    if not os.path.exists(json_path):
        sys.stderr.write(f"❌ ERROR: Файл {json_path} не найден.\n")
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅ Чанки ({len(data)} шт.) загружены из {json_path}")
        return data
    except Exception as e:
        sys.stderr.write(f"❌ ERROR: Не удалось загрузить/декодировать {json_path}: {e}\n")
        return []

def format_table_to_markdown(table_data: List[List[str]], headers: List[str] = None) -> str:
    """Преобразует табличные данные в Markdown формат."""
    if not table_data:
        return ""
        
    # Если заголовки не переданы, используем первую строку как заголовки
    if not headers and table_data:
        headers = table_data[0]
        table_data = table_data[1:]
        
    if not headers:
        return ""
        
    # Создаем заголовок таблицы
    markdown = "| " + " | ".join(str(h) for h in headers) + " |\n"
    markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    
    # Добавляем строки данных
    for row in table_data:
        # Выравниваем количество колонок с заголовками
        row_data = row[:len(headers)] + [''] * (len(headers) - len(row))
        markdown += "| " + " | ".join(str(cell) for cell in row_data) + " |\n"
        
    return markdown.strip()

# --- END OF FILE common_utils.py ---