# --- START OF FILE common_utils.py ---
import re
import json
import hashlib
import os
from datetime import datetime
import numpy as np
import sys
from typing import Any, Dict, List, Optional

def clean_text(text: Optional[str]) -> str:
    """Очищает текст от лишних пробелов, неразрывных пробелов и множественных переносов строк."""
    if not isinstance(text, str):
        return ""
    text = text.replace('\xa0', ' ')  # Заменяем неразрывный пробел
    text = re.sub(r'[ \t]+', ' ', text)  # Заменяем множественные пробелы/табы на один пробел
    text = re.sub(r'\n\s*\n', '\n\n', text) # Убираем пустые строки между переносами
    text = re.sub(r'\n{3,}', '\n\n', text) # Оставляем не более двух переносов подряд
    return text.strip()

def hash_chunk(text: str, document_name: str, chunk_index: int) -> str:
    """Генерирует MD5 хеш для идентификации чанка."""
    return hashlib.md5(f"{document_name}-{chunk_index}-{text}".encode("utf-8")).hexdigest()

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

def save_chunks_json(chunks: List[Dict], output_path: str):
    """Сохраняет список чанков в JSON файл."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2, default=serialize_meta)
        print(f"💾 Чанки ({len(chunks)} шт.) сохранены в {output_path}")
    except Exception as e:
        sys.stderr.write(f"❌ ERROR: Не удалось сохранить чанки в {output_path}: {e}\n")
        # traceback.print_exc() # Раскомментировать для детальной отладки

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

def format_table_to_markdown(table_data: List[Dict[str, Any]], headers: List[str]) -> str:
    """Форматирует данные таблицы в Markdown."""
    if not isinstance(table_data, list) or not isinstance(headers, list) or not headers:
        return "[Неверные данные для таблицы]"

    # Экранируем символы пайпа в заголовках и данных
    escaped_headers = [str(h).replace("|", "\\|") for h in headers]
    md_header = "| " + " | ".join(escaped_headers) + " |"
    md_separator = "|-" + "-|".join(['-' * max(3, len(str(h))) for h in escaped_headers]) + "-|" # Минимальная ширина 3

    md_rows = []
    for row_dict in table_data:
        if isinstance(row_dict, dict):
            row_values = [
                str(row_dict.get(h, '')).replace("|", "\\|").replace("\n", " ") # Убираем переносы строк внутри ячеек
                for h in headers
            ]
            md_rows.append("| " + " | ".join(row_values) + " |")

    return md_header + "\n" + md_separator + "\n" + "\n".join(md_rows)

# --- END OF FILE common_utils.py ---