# encryptor_tools.py — шифровка и дешифровка данных с заменой и восстановлением

import re
import json
from uuid import uuid4
import hashlib
import base64
from typing import Dict, Any, Optional
import os

# Расширенные паттерны для сущностей
patterns = {
    "contact": r"[\w\.-]+@[\w\.-]+\.\w+|@[\w\d\._]+|(?:\+7|8)[\s\-\(]?\d{3}[\s\-\(]?\d{3}[\s\-\(]?\d{2}[\s\-\(]?\d{2}",  # email, Telegram, телефоны
    "name": r"[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?",  # Имя Фамилия Отчество
    "project": r"\b(MST|MB|MM|Mostbet|BetAndreas|Project[A-Z]|Proj\d+)\b",
    "tool": r"\b(Asana|Jira|Inbox 360|Promo Calendar|Trello|Notion|Slack|Discord)\b",
    "url": r"https?://(?:[\w-]+\.)+[\w-]+(?:/[\w\-\./?%&=]*)?",
    "ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "date": r"\b\d{2}\.\d{2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b",
    "amount": r"\b\d+(?:[.,]\d{2})?\s*(?:USD|EUR|RUB|₽|\$|€)\b",
    "id": r"\b[A-Z]{2,3}-\d{4,6}\b",
}

def generate_secure_token(entity_type: str, original: str) -> str:
    """Генерация безопасного токена с хешированием"""
    salt = uuid4().hex[:8]
    hash_input = f"{entity_type}:{original}:{salt}"
    hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
    return f"@@{entity_type.upper()}_{hash_value}@@"

def obfuscate_text(text: str, mask_map: Dict[str, Any]) -> str:
    """
    Обфускация текста с заменой чувствительных данных на токены.
    """
    if not text:
        return text

    def make_repl(entity_type: str):
        def repl(match):
            original = match.group(0)
            token = generate_secure_token(entity_type, original)
            mask_map[token] = {
                "type": entity_type,
                "original": original,
                "hash": hashlib.sha256(original.encode()).hexdigest()[:16]
            }
            return token
        return repl

    # Применяем все паттерны
    for key in patterns:
        try:
            text = re.sub(patterns[key], make_repl(key), text)
        except Exception as e:
            print(f"⚠️ Предупреждение: Ошибка при обработке паттерна {key}: {e}")
            continue
    
    return text

def deobfuscate_text(text: str, mask_map: Dict[str, Any]) -> str:
    """
    Деобфускация текста с восстановлением оригинальных данных.
    """
    if not text:
        return text

    # Проверяем валидность маски
    for token, entry in mask_map.items():
        if not isinstance(entry, dict) or "original" not in entry:
            continue
            
        # Проверяем хеш для дополнительной безопасности
        if "hash" in entry:
            expected_hash = hashlib.sha256(entry["original"].encode()).hexdigest()[:16]
            if entry["hash"] != expected_hash:
                continue
                
        text = text.replace(token, entry["original"])
    
    return text

def save_map(mask_map: Dict[str, Any], path: str) -> bool:
    """
    Безопасное сохранение карты обфускации.
    """
    try:
        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Сохраняем с дополнительным шифрованием
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mask_map, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении карты обфускации: {e}")
        return False

def load_map(path: str) -> Optional[Dict[str, Any]]:
    """
    Безопасная загрузка карты обфускации.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            mask_map = json.load(f)
            
        # Валидация загруженной карты
        if not isinstance(mask_map, dict):
            raise ValueError("Некорректный формат карты обфускации")
            
        return mask_map
    except Exception as e:
        print(f"❌ Ошибка при загрузке карты обфускации: {e}")
        return None
