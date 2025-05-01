# --- START OF FILE chunker.py (Исправлено экранирование) ---
import re
from typing import List, Optional, Callable

def _split_text_with_regex(text: str, separator: str, keep_separator: bool) -> List[str]:
    """Разделяет текст по регулярному выражению сепаратора."""
    if separator:
        # --- ИСПРАВЛЕНИЕ: Экранируем сепаратор перед использованием в re.split ---
        escaped_separator = re.escape(separator)
        if keep_separator:
            # Используем группы для сохранения сепаратора
            splits = re.split(f"({escaped_separator})", text)
            # Объединяем текст и сепаратор, фильтруем пустые строки
            merged = []
            for i in range(0, len(splits), 2):
                part = splits[i]
                sep = splits[i+1] if i+1 < len(splits) else ''
                if part or sep: # Добавляем, если есть текст или сепаратор
                    merged.append(part + sep)
            # Если последний элемент - текст без сепаратора
            if len(splits) % 2 != 0 and splits[-1]:
                 merged.append(splits[-1])
            return [s for s in merged if s] # Фильтруем пустые на всякий случай
        else:
            # Просто разделяем по экранированному сепаратору
            return [s for s in re.split(escaped_separator, text) if s]
    else:
        # Разделяем по символам, если нет сепаратора (например, последний уровень рекурсии)
        return list(text)


# --- Остальной код SimpleRecursiveTextSplitter без изменений ---

def _join_docs(docs: List[str], separator: str) -> Optional[str]:
    """Объединяет строки с сепаратором."""
    text = separator.join(docs)
    return text.strip() if text else None

class SimpleRecursiveTextSplitter:
    """
    Простой рекурсивный сплиттер текста.
    Старается разбивать по сепараторам, пока чанк не станет меньше chunk_size.
    """
    def __init__(
        self,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True, # Рекомендуется True для сохранения контекста
        chunk_size: int = 800,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be smaller than chunk size.")

        self._separators = separators or ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]
        self._keep_separator = keep_separator
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Рекурсивно разделяет текст по сепараторам."""
        final_chunks: List[str] = []
        # Базовый случай рекурсии: текст меньше или равен размеру чанка
        if self._length_function(text) <= self._chunk_size:
            return [text] # Возвращаем как один чанк

        # Если сепараторы закончились, а текст все еще большой, режем по размеру
        if not separators:
            return self._split_by_size(text)

        # Берем первый сепаратор из списка
        separator = separators[0]
        # Оставшиеся сепараторы для следующего уровня рекурсии
        next_separators = separators[1:]

        try:
            # Разделяем текст по текущему сепаратору
            splits = _split_text_with_regex(text, separator, self._keep_separator)
        except re.error as e:
             # Если даже экранированный сепаратор вызвал ошибку (маловероятно)
             print(f"⚠️ Regex error with separator '{separator}': {e}. Trying next separators.")
             # Пробуем разбить этот же текст оставшимися сепараторами
             return self._split_text(text, next_separators)

        # --- Логика сборки чанков с учетом overlap ---
        current_chunk_parts: List[str] = []
        current_length = 0
        for part in splits:
             part_len = self._length_function(part)

             # Если добавление следующей части превысит размер чанка
             if current_length + part_len > self._chunk_size and current_chunk_parts:
                 # Собираем текущий чанк
                 chunk_to_add = _join_docs(current_chunk_parts, "")
                 if chunk_to_add:
                      # Если чанк все еще слишком большой, рекурсивно делим его дальше
                      if self._length_function(chunk_to_add) > self._chunk_size:
                           final_chunks.extend(self._split_text(chunk_to_add, next_separators))
                      else:
                           final_chunks.append(chunk_to_add)

                 # Начинаем новый чанк, учитывая overlap
                 # Ищем точку для overlap в *собранном* предыдущем чанке
                 overlap_start_index = max(0, self._length_function(chunk_to_add) - self._chunk_overlap)
                 overlap_text = chunk_to_add[overlap_start_index:]

                 # Новый чанк начинается с оверлапа и текущей части
                 # Если оверлап + часть > размера чанка (очень большая часть)
                 if self._length_function(overlap_text) + part_len > self._chunk_size:
                      # Добавляем оверлап как отдельный чанк (или его часть)
                      if overlap_text:
                          if self._length_function(overlap_text) > self._chunk_size:
                               final_chunks.extend(self._split_text(overlap_text, next_separators))
                          else:
                               final_chunks.append(overlap_text)
                      # А большую часть обрабатываем рекурсивно отдельно
                      if self._length_function(part) > self._chunk_size:
                           final_chunks.extend(self._split_text(part, next_separators))
                           current_chunk_parts = [] # Начинаем с нуля
                           current_length = 0
                      else:
                           # Часть помещается, начинаем новый чанк с нее
                           current_chunk_parts = [part]
                           current_length = part_len
                 else:
                     # Оверлап + часть помещаются, начинаем новый чанк с них
                     current_chunk_parts = [overlap_text, part]
                     current_length = self._length_function(overlap_text) + part_len

             # Если добавление части не превышает размер чанка
             else:
                 current_chunk_parts.append(part)
                 current_length += part_len

        # Добавляем последний накопленный чанк
        if current_chunk_parts:
             last_chunk = _join_docs(current_chunk_parts, "")
             if last_chunk:
                 # Если последний чанк все еще большой, делим его дальше
                 if self._length_function(last_chunk) > self._chunk_size:
                     final_chunks.extend(self._split_text(last_chunk, next_separators))
                 else:
                     final_chunks.append(last_chunk)

        # Фильтруем пустые строки на выходе
        return [chunk for chunk in final_chunks if chunk and chunk.strip()]


    def _split_by_size(self, text: str) -> List[str]:
        """Просто режет текст на куски фиксированного размера с перекрытием."""
        if self._length_function(text) <= self._chunk_size:
             return [text]

        chunks = []
        start_index = 0
        while start_index < self._length_function(text):
            end_index = start_index + self._chunk_size
            chunk = text[start_index:end_index]
            chunks.append(chunk)
            # Сдвигаемся на размер чанка минус перекрытие
            start_index += self._chunk_size - self._chunk_overlap
            # Если overlap большой, можем зайти в бесконечный цикл, если chunk_size ~= chunk_overlap
            if start_index == 0 and len(chunks) > 1:
                 print(f"⚠️ Potential infinite loop in _split_by_size detected. Breaking.")
                 break # Предохранитель
            # Предохранитель от слишком большого сдвига назад при большом overlap
            if start_index < end_index - self._chunk_size / 2 and self._chunk_overlap > 0 :
                 # Если сдвинулись меньше чем на половину чанка назад, это странно
                 pass # Пока просто наблюдаем

        return chunks


    def split_text(self, text: str) -> List[str]:
        """Основной метод для разделения текста."""
        if not text:
            return []
        # Начинаем разделение с основного списка сепараторов
        return self._split_text(text, self._separators)

# --- END OF FILE chunker.py ---