# --- START OF FILE chunker.py (Исправлено экранирование) ---
import re
from typing import List, Optional, Callable, Dict, Any

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

class SemanticDocumentChunker:
    """
    Семантический чанкер документов, который разбивает текст по логическим блокам
    и собирает метаданные о ссылках, контактах и структуре.
    """
    def __init__(
        self,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        overlap_size: int = 100,
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        
        # Регулярные выражения для поиска специальных элементов
        self.link_pattern = re.compile(
            r'(?:https?://[^\s<>"]+|www\.[^\s<>"]+)|'  # URL
            r'(?:\[([^\]]+)\]\(([^)]+)\))|'  # Markdown links
            r'(?:<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>)'  # HTML links
        )
        self.email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
        self.telegram_pattern = re.compile(r'@[\w_]+')
        self.tag_pattern = re.compile(r'\[([A-Z]+)\]')
        
        # Паттерны для определения логических блоков
        self.section_patterns = [
            (r'^#{1,6}\s+(.+)$', 'heading'),  # Markdown headings
            (r'^\d+\.\s+(.+)$', 'numbered_list'),  # Numbered lists
            (r'^[-*]\s+(.+)$', 'bullet_list'),  # Bullet lists
            (r'^Q:\s*(.+)$', 'question'),  # Questions
            (r'^A:\s*(.+)$', 'answer'),  # Answers
            (r'^\s*[-*]\s*\[\s*\]\s*(.+)$', 'checkbox'),  # Checkboxes
        ]
        
        # Паттерны для определения таблиц
        self.table_patterns = [
            (r'^\|.*\|$', 'markdown_table'),  # Markdown таблицы
            (r'^\s*[-+]+\s*$', 'markdown_table_separator'),  # Разделитель Markdown таблицы
            (r'^\s*<table.*>.*</table>\s*$', 'html_table'),  # HTML таблицы
        ]
        
    def _is_table(self, text: str) -> bool:
        """Определяет, является ли текст таблицей."""
        lines = text.strip().split('\n')
        if len(lines) < 3:  # Таблица должна иметь минимум заголовок, разделитель и строку данных
            return False
            
        # Проверяем первую строку на соответствие формату таблицы
        for pattern, _ in self.table_patterns:
            if re.match(pattern, lines[0]):
                return True
                
        return False
        
    def _split_table(self, text: str, headers: List[str] = None) -> List[Dict[str, Any]]:
        """Разбивает таблицу на логические части."""
        lines = text.strip().split('\n')
        chunks = []
        current_chunk = []
        
        # Если таблица маленькая, возвращаем её как один чанк
        if len(text) <= self.max_chunk_size:
            return [{
                'text': text,
                'metadata': {
                    'chunk_type': 'table',
                    'table_headers': headers or [],
                    'is_complete_table': True
                }
            }]
            
        # Разбиваем таблицу на части по строкам
        for line in lines:
            current_chunk.append(line)
            chunk_text = '\n'.join(current_chunk)
            
            if len(chunk_text) >= self.max_chunk_size:
                # Сохраняем текущий чанк
                chunks.append({
                    'text': chunk_text,
                    'metadata': {
                        'chunk_type': 'table',
                        'table_headers': headers or [],
                        'is_complete_table': False
                    }
                })
                # Начинаем новый чанк с последней строки для контекста
                current_chunk = [line]
                
        # Добавляем последний чанк
        if current_chunk:
            chunks.append({
                'text': '\n'.join(current_chunk),
                'metadata': {
                    'chunk_type': 'table',
                    'table_headers': headers or [],
                    'is_complete_table': False
                }
            })
            
        return chunks
        
    def _extract_links(self, text: str) -> List[Dict[str, str]]:
        """Извлекает все ссылки из текста с контекстом."""
        links = []
        for match in self.link_pattern.finditer(text):
            url = match.group(0)
            anchor_text = match.group(1) if match.group(1) else url
            
            # Определяем тип ссылки
            link_type = 'unknown'
            if 'confluence' in url.lower():
                link_type = 'confluence'
            elif 'jira' in url.lower():
                link_type = 'jira'
            elif 'asana' in url.lower():
                link_type = 'asana'
            elif '@' in url:
                link_type = 'email'
                
            # Получаем контекст ссылки (предыдущее и следующее предложение)
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end]
            
            links.append({
                'url': url,
                'anchor_text': anchor_text,
                'context_snippet': context,
                'link_type': link_type
            })
        return links
        
    def _extract_contacts(self, text: str) -> List[Dict[str, str]]:
        """Извлекает контакты из текста."""
        contacts = []
        
        # Ищем email
        for email in self.email_pattern.finditer(text):
            contacts.append({
                'type': 'email',
                'value': email.group(0)
            })
            
        # Ищем Telegram
        for telegram in self.telegram_pattern.finditer(text):
            contacts.append({
                'type': 'telegram',
                'value': telegram.group(0)
            })
            
        return contacts
        
    def _identify_block_type(self, text: str) -> str:
        """Определяет тип логического блока."""
        for pattern, block_type in self.section_patterns:
            if re.match(pattern, text.strip()):
                return block_type
        return 'text'
        
    def _create_chunk_metadata(
        self,
        text: str,
        block_type: str,
        heading: Optional[str] = None,
        section: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создает метаданные для чанка."""
        return {
            'chunk_type': block_type,
            'heading': heading,
            'section': section,
            'links': self._extract_links(text),
            'contacts': self._extract_contacts(text),
            'tags': [tag.group(1) for tag in self.tag_pattern.finditer(text)]
        }
        
    def _split_into_logical_blocks(self, text: str) -> List[Dict[str, Any]]:
        """Разбивает текст на логические блоки с метаданными."""
        blocks = []
        current_block = []
        current_heading = None
        current_section = None
        
        for line in text.split('\n'):
            # Проверяем, является ли строка заголовком
            heading_match = re.match(r'^#{1,6}\s+(.+)$', line)
            if heading_match:
                # Если есть накопленный блок, сохраняем его
                if current_block:
                    block_text = '\n'.join(current_block)
                    blocks.append({
                        'text': block_text,
                        'metadata': self._create_chunk_metadata(
                            block_text,
                            self._identify_block_type(block_text),
                            current_heading,
                            current_section
                        )
                    })
                    current_block = []
                
                current_heading = heading_match.group(1)
                continue
                
            # Проверяем, является ли строка началом новой секции
            section_match = re.match(r'^##\s+(.+)$', line)
            if section_match:
                current_section = section_match.group(1)
                continue
                
            # Добавляем строку в текущий блок
            current_block.append(line)
            
            # Если блок стал слишком большим, разбиваем его
            if len('\n'.join(current_block)) > self.max_chunk_size:
                block_text = '\n'.join(current_block)
                blocks.append({
                    'text': block_text,
                    'metadata': self._create_chunk_metadata(
                        block_text,
                        self._identify_block_type(block_text),
                        current_heading,
                        current_section
                    )
                })
                current_block = []
                
        # Добавляем последний блок
        if current_block:
            block_text = '\n'.join(current_block)
            blocks.append({
                'text': block_text,
                'metadata': self._create_chunk_metadata(
                    block_text,
                    self._identify_block_type(block_text),
                    current_heading,
                    current_section
                )
            })
            
        return blocks
        
    def split_document(self, text: str, headers: List[str] = None) -> List[Dict[str, Any]]:
        """
        Разбивает документ на семантические чанки с метаданными.
        Возвращает список словарей с текстом и метаданными.
        """
        # Если это таблица, используем специальную обработку
        if self._is_table(text):
            return self._split_table(text, headers)
            
        # Иначе используем стандартную обработку
        blocks = self._split_into_logical_blocks(text)
        
        # Объединяем маленькие блоки одного типа
        merged_blocks = []
        current_block = None
        
        for block in blocks:
            if not current_block:
                current_block = block
                continue
                
            # Если текущий блок того же типа и их объединение не превышает max_chunk_size
            if (current_block['metadata']['chunk_type'] == block['metadata']['chunk_type'] and
                len(current_block['text'] + '\n' + block['text']) <= self.max_chunk_size):
                current_block['text'] += '\n' + block['text']
                # Объединяем метаданные
                current_block['metadata']['links'].extend(block['metadata']['links'])
                current_block['metadata']['contacts'].extend(block['metadata']['contacts'])
                current_block['metadata']['tags'].extend(block['metadata']['tags'])
            else:
                merged_blocks.append(current_block)
                current_block = block
                
        if current_block:
            merged_blocks.append(current_block)
            
        return merged_blocks

# --- END OF FILE chunker.py ---