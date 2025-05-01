# encryptor_tools.py — шифровка и дешифровка данных с заменой и восстановлением

import re
import json
from uuid import uuid4

# Паттерны для сущностей (контакты, проекты, инструменты и т.д.)
patterns = {
    "contact": r"[\w\.-]+@[\w\.-]+|@[\w\d\._]+",  # email и Telegram
    "name": r"[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+",             # Имя Фамилия
    "project": r"\b(MST|MB|MM|Mostbet|BetAndreas)\b",
    "tool": r"Asana|Jira|Inbox 360|Promo Calendar",
}

def obfuscate_text(text: str, mask_map: dict) -> str:
    def make_repl(entity_type):
        def repl(match):
            original = match.group(0)
            token = f"@@{entity_type.upper()}_{uuid4().hex[:6]}@@"
            mask_map[token] = {"type": entity_type, "original": original}
            return token
        return repl

    for key in patterns:
        text = re.sub(patterns[key], make_repl(key), text)
    return text

def deobfuscate_text(text: str, mask_map: dict) -> str:
    for token, entry in mask_map.items():
        text = text.replace(token, entry["original"])
    return text

def save_map(mask_map: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mask_map, f, ensure_ascii=False, indent=2)

def load_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
