# --- START OF FILE document_parser.py ---
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple, Generator

import pandas as pd
import pdfplumber
import docx
from tqdm import tqdm
# import openpyxl # Не нужен явный импорт, pandas его использует

# Используем относительные импорты
# Если запускаете не как пакет, замените на 'from common_utils import ...'
try:
    from .common_utils import clean_text, format_table_to_markdown
except ImportError:
    # Прямой импорт для случая плоской структуры файлов
    try:
        from common_utils import clean_text, format_table_to_markdown
        print("✅ common_utils imported directly into document_parser.")
    except ImportError as e:
        sys.stderr.write(f"❌ CRITICAL: Failed to import common_utils in document_parser. Error: {e}\n")
        sys.exit(1)

# --- Структура для возвращаемых "сырых" блоков ---
class RawContentBlock:
    """Структура для представления сырого блока контента из документа."""
    def __init__(self, type: str, content: Any, source_info: Dict):
        self.type: str = type # 'text', 'table', 'excel_row'
        self.content: Any = content # str для текста, List[Dict] для таблицы, Dict для строки Excel
        self.source_info: Dict = source_info # page_number, element_index, headers, etc.

    def __repr__(self):
        content_len_str = 'N/A'
        if isinstance(self.content, (str, list, dict)):
            try:
                content_len_str = str(len(self.content))
            except TypeError:
                pass # Не у всех объектов есть len
        return (f"RawContentBlock(type='{self.type}', "
                f"source='{self.source_info.get('document_name', 'Unknown')}', "
                f"page={self.source_info.get('page_number', 'N/A')}, "
                f"content_len={content_len_str})")

# --- PDF Parser ---
def parse_pdf(file_path: str) -> Generator[RawContentBlock, None, None]:
    """Извлекает текст и таблицы из PDF как генератор RawContentBlock."""
    document_name = os.path.basename(file_path)
    all_pdf_hyperlinks = []
    try:
        with pdfplumber.open(file_path) as pdf:
            # Сначала собираем все гиперссылки
            for p_idx, page in enumerate(pdf.pages):
                try:
                    # Проверяем наличие атрибута hyperlinks перед доступом
                    if hasattr(page, 'hyperlinks') and page.hyperlinks:
                        all_pdf_hyperlinks.extend([
                            {'url': link.get('uri'), 'page': p_idx + 1, 'text': link.get('title', '')}
                            for link in page.hyperlinks if link.get('uri') # Только если есть URL
                        ])
                except Exception as e:
                    sys.stderr.write(f"  ⚠️ PDF link extraction error p.{p_idx+1} in '{document_name}': {e}\n")
            # Дедупликация ссылок по URL
            unique_hyperlinks = list({link['url']: link for link in all_pdf_hyperlinks}.values())
            print(f"  🔗 PDF Links found in '{document_name}': {len(unique_hyperlinks)}")

            # Обрабатываем страницы
            for i, page in enumerate(tqdm(pdf.pages, desc=f"  -> PDF Pages '{document_name}'", unit="page", leave=False)):
                page_num = i + 1
                # Гиперссылки для текущей страницы
                page_hyperlinks = [h for h in unique_hyperlinks if h.get('page') == page_num]

                # Извлекаем таблицы
                try:
                    # Настройки можно подбирать для лучшего результата
                    tables = page.extract_tables({
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "intersection_tolerance": 3, # Уменьшил для точности
                        "snap_tolerance": 3,
                    })
                    if tables:
                        for table_idx, table_raw in enumerate(tables):
                            if not table_raw or len(table_raw) < 1: continue # Пропускаем пустые таблицы

                            # Очищаем заголовки, заменяем None/пустые строки на Col_N
                            headers = [clean_text(h) if h and clean_text(h) else f"Col_{j}" for j, h in enumerate(table_raw[0])]
                            table_data: List[Dict[str, Any]] = []

                            # Обрабатываем строки данных (начиная со второй строки)
                            if len(table_raw) > 1:
                                for row_cells in table_raw[1:]:
                                    if not row_cells: continue # Пропускаем пустые строки
                                    # Выравниваем кол-во ячеек с кол-вом заголовков
                                    processed_cells = row_cells[:len(headers)] + [''] * (len(headers) - len(row_cells))
                                    # Создаем словарь, очищая значения, берем только непустые ячейки
                                    row_dict = {
                                        headers[j]: clean_text(cell)
                                        for j, cell in enumerate(processed_cells) if cell is not None and clean_text(str(cell)) # Только непустые ячейки после очистки
                                    }
                                    if row_dict: # Добавляем строку только если в ней есть данные
                                        table_data.append(row_dict)

                            # Отдаем таблицу только если есть заголовки и данные
                            if headers and table_data:
                                source_info = {
                                    "document_name": document_name,
                                    "page_number": page_num,
                                    "table_index_on_page": table_idx + 1, # 1-based index
                                    "headers": headers,
                                    "document_hyperlinks": unique_hyperlinks # Передаем все ссылки документа
                                }
                                yield RawContentBlock(type='table', content=table_data, source_info=source_info)
                            elif headers and not table_data:
                                print(f"    ℹ️ PDF Table on p.{page_num} has headers but no data. Skipping.")
                            # else: # Случай: нет заголовков или нет данных (или и то и другое)
                                # print(f"    ℹ️ PDF Table on p.{page_num} is empty or lacks headers. Skipping.")

                except Exception as e:
                    sys.stderr.write(f"  ⚠️ PDF table extraction error p.{page_num} in '{document_name}': {e}\n")
                    # traceback.print_exc() # Для отладки

                # Извлекаем текст (после таблиц, т.к. extract_text может включать текст таблиц)
                # Используем x_tolerance и y_tolerance для лучшего сохранения структуры
                page_text_raw = page.extract_text(x_tolerance=2, y_tolerance=3, layout=False, keep_blank_chars=False)
                page_text_cleaned = clean_text(page_text_raw)

                # Отдаем текстовый блок, если он не пустой
                if page_text_cleaned:
                    source_info = {
                        "document_name": document_name,
                        "page_number": page_num,
                        "document_hyperlinks": unique_hyperlinks # Передаем все ссылки документа
                        # "page_hyperlinks": page_hyperlinks # Можно передавать ссылки только для этой страницы, если нужно
                    }
                    yield RawContentBlock(type='text', content=page_text_cleaned, source_info=source_info)

    except Exception as e:
        sys.stderr.write(f"❌ CRITICAL PDF Error processing '{document_name}': {e}\n")
        traceback.print_exc()

# --- DOCX Parser ---
def parse_docx(file_path: str) -> Generator[RawContentBlock, None, None]:
    """Извлекает текст и таблицы из DOCX как генератор RawContentBlock."""
    document_name = os.path.basename(file_path)
    unique_hyperlinks_docx = [] # TODO: Реализовать извлечение гиперссылок DOCX
    # print(f"  🔗 DOCX links extraction not implemented yet for '{document_name}'.") # Убрал вывод

    try:
        doc = docx.Document(file_path)
        body_elements = list(doc.element.body) # Получаем все дочерние элементы body
        current_heading = "Общее"
        current_text_accumulator = ""

        for idx, element in enumerate(tqdm(body_elements, desc=f"  -> DOCX Elements '{document_name}'", unit="elem", leave=False)):
            # Определяем тип элемента (параграф или таблица)
            # Используем local-name() для независимости от префикса пространства имен (w:)
            is_paragraph = hasattr(element, 'xpath') and ('p' in element.xpath('local-name(.)'))
            is_table = hasattr(element, 'xpath') and ('tbl' in element.xpath('local-name(.)'))

            if is_paragraph:
                try:
                    # Создаем объект Paragraph из элемента
                    p = docx.text.paragraph.Paragraph(element, doc)
                    para_text = clean_text(p.text)

                    # Проверяем стиль на заголовок (регистронезависимо)
                    style_name = p.style.name.lower() if p.style and p.style.name else ""
                    is_heading_style = style_name.startswith(('heading', 'заголовок', 'title', 'название'))

                    # Если это заголовок и он не пустой
                    if is_heading_style and para_text:
                        # Если был накоплен текст перед этим заголовком, отдаем его
                        if current_text_accumulator.strip():
                            source_info = {
                                "document_name": document_name,
                                "current_heading": current_heading, # Заголовок, к которому относился текст
                                "document_hyperlinks": unique_hyperlinks_docx
                            }
                            yield RawContentBlock(type='text', content=current_text_accumulator.strip(), source_info=source_info)

                        # Обновляем текущий заголовок и сбрасываем аккумулятор текста
                        current_heading = para_text
                        current_text_accumulator = "" # Начинаем новый блок текста под новым заголовком
                        # print(f"\n    --- DOCX Heading Found: '{current_heading}' ---") # Убрал вывод
                    # Если это обычный параграф с текстом
                    elif para_text:
                        # Добавляем текст параграфа к аккумулятору, разделяя двойным переносом
                        current_text_accumulator += para_text + "\n\n"

                except Exception as e:
                    # Ловим ошибки при обработке конкретного параграфа
                    sys.stderr.write(f"  ⚠️ DOCX Paragraph processing error (element {idx}) in '{document_name}': {e}\n")
                    continue # Пропускаем этот параграф

            elif is_table:
                # Перед обработкой таблицы отдаем накопленный текстовый блок
                if current_text_accumulator.strip():
                    source_info = {
                        "document_name": document_name,
                        "current_heading": current_heading,
                        "document_hyperlinks": unique_hyperlinks_docx
                    }
                    yield RawContentBlock(type='text', content=current_text_accumulator.strip(), source_info=source_info)
                    current_text_accumulator = "" # Сбрасываем аккумулятор

                # Обрабатываем таблицу
                # print(f"    --- DOCX Table Found (element index {idx}) ---") # Убрал вывод
                try:
                    table_obj = docx.table.Table(element, doc)
                    if not table_obj.rows:
                         # print("      Skipping empty table (no rows).") # Убрал вывод
                         continue

                    # Извлекаем заголовки из первой строки, очищая их
                    headers = [clean_text(cell.text) for cell in table_obj.rows[0].cells]
                    # Определяем, есть ли реальные заголовки (не пустые и не просто 'Col_N')
                    has_actual_headers = any(h for h in headers)
                    start_row_index = 1 if has_actual_headers else 0

                    # Если заголовков нет, генерируем их как Col_N
                    if not has_actual_headers:
                         num_cols = len(table_obj.rows[0].cells) if table_obj.rows else 0
                         if num_cols == 0: continue # Пропускаем, если и колонок нет
                         headers = [f"Col_{j}" for j in range(num_cols)]
                         start_row_index = 0 # Начинаем с первой строки, раз заголовков не было

                    table_data: List[Dict[str, Any]] = []
                    # Итерируемся по строкам данных
                    for r_idx, row in enumerate(table_obj.rows[start_row_index:], start=start_row_index):
                        row_values = [clean_text(cell.text) for cell in row.cells]
                        # Создаем словарь строки, обрезая лишние значения или дополняя пустыми
                        # Включаем только непустые ячейки в словарь
                        row_dict = {
                            headers[j]: val
                            for j, val in enumerate(row_values)
                            if j < len(headers) and val # Условие: индекс в пределах заголовков и значение не пустое
                        }
                        # Добавляем строку только если она содержит хоть какие-то данные
                        if row_dict:
                            table_data.append(row_dict)

                    # Отдаем блок таблицы, только если есть данные
                    if table_data:
                         source_info = {
                             "document_name": document_name,
                             "table_index_in_doc": idx + 1, # 1-based index
                             "current_heading": current_heading, # Заголовок секции, где таблица
                             "headers": headers,
                             "document_hyperlinks": unique_hyperlinks_docx
                         }
                         yield RawContentBlock(type='table', content=table_data, source_info=source_info)
                         # print(f"      Table {idx+1} processed successfully.") # Убрал вывод
                    # else:
                        # print(f"      Table {idx+1} resulted in no data after processing, skipping.") # Убрал вывод

                except Exception as e:
                    sys.stderr.write(f"  ⚠️ DOCX Table processing error (element {idx}) in '{document_name}': {e}\n")
                    traceback.print_exc() # Для отладки

            else:
                # Неизвестный тип элемента верхнего уровня, пропускаем
                # print(f"  ℹ️ Skipping unknown top-level element (index {idx}) in '{document_name}'")
                pass

        # После цикла отдаем последний накопленный текстовый блок, если он есть
        if current_text_accumulator.strip():
            source_info = {
                "document_name": document_name,
                "current_heading": current_heading,
                "document_hyperlinks": unique_hyperlinks_docx
            }
            yield RawContentBlock(type='text', content=current_text_accumulator.strip(), source_info=source_info)

        # print(f"  Finished iterating through DOCX elements for '{document_name}'.") # Убрал вывод

    except Exception as e:
        # Ловим ошибки на уровне открытия/основной обработки DOCX
        sys.stderr.write(f"❌ CRITICAL DOCX Error processing '{document_name}': {e}\n")
        traceback.print_exc()

# --- Excel Parser (v17 - Refined, using RawContentBlock) ---
def parse_excel(xlsx_path: str) -> Generator[RawContentBlock, None, None]:
    """Обрабатывает Excel файл, представляя каждую строку как RawContentBlock 'excel_row'."""
    document_name = os.path.basename(xlsx_path)
    # print(f"📄 Processing Excel file: {document_name}") # Убрал вывод
    try:
        # engine=None позволяет pandas автоматически выбрать (обычно openpyxl)
        xls = pd.ExcelFile(xlsx_path, engine=None)
        # Проходим по всем листам
        for sheet_name in tqdm(xls.sheet_names, desc=f"  -> Excel Sheets '{document_name}'", unit="sheet", leave=False):
            # print(f"  -- Processing sheet: '{sheet_name}'") # Убрал вывод
            df: pd.DataFrame
            headers: List[str] = []
            header_row_index = 0 # Индекс строки, которую мы считаем заголовком (0-based)
            try:
                # --- Чтение и поиск заголовка ---
                # 1. Читаем без заголовка, чтобы проанализировать первые строки
                #    dtype=str чтобы избежать автоматического определения типов данных pandas
                df_raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None, dtype=str).fillna('')
                if df_raw.empty:
                    # print(f"    Sheet '{sheet_name}' is empty. Skipping.") # Убрал вывод
                    continue

                # 2. Эвристика для поиска заголовка в первых N строках (напр., 5)
                potential_header_row = -1 # Индекс строки-кандидата в заголовки
                max_keywords_found = 1 # Минимальное кол-во ключевых слов для признания заголовком
                keywords = {"position", "email", "tg", "telegram", "отдел", "department",
                            "name", "имя", "фамилия", "должность", "fi", "team", "команда",
                            "geo", "ссылка", "форма", "название", "описание", "ответственный",
                            "responsible", "role", "роль", "contact", "контакт", "status", "статус"}

                for r_idx in range(min(5, len(df_raw))):
                    row_values = [str(c).lower().strip() for c in df_raw.iloc[r_idx].values if str(c).strip()]
                    if not row_values: continue # Пропускаем пустые строки
                    row_text = " ".join(row_values)
                    keywords_found = sum(1 for kw in keywords if kw in row_text)

                    # Считаем заголовком, если нашли достаточно ключевых слов
                    if keywords_found >= max_keywords_found:
                         potential_header_row = r_idx
                         max_keywords_found = keywords_found # Обновляем макс. найденных (можно убрать для простоты)
                         break # Нашли первый подходящий - используем его

                # 3. Перечитываем DataFrame с найденным заголовком или без него
                if potential_header_row != -1:
                    header_row_index = potential_header_row
                    # print(f"    Detected header row index: {header_row_index}") # Убрал вывод
                    # Читаем снова, используя найденный заголовок, dtype=str
                    df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=header_row_index, dtype=str).fillna('')
                else:
                    # print(f"    ⚠️ Could not detect header row. Reading without header.") # Убрал вывод
                    df = df_raw # Используем уже прочитанный df_raw
                    # Генерируем заголовки "Col_N"
                    df.columns = [f"Col_{i}" for i in range(len(df.columns))]

                # print(f"    Read {len(df)} data rows from sheet '{sheet_name}'.") # Убрал вывод
                if df.empty: continue

                # --- Очистка и подготовка DataFrame ---
                # Нормализуем заголовки: в нижний регистр, убираем пробелы, заменяем переносы
                df.columns = [str(col).strip().lower().replace('\n', ' ').replace('\r', '') for col in df.columns]
                # Удаляем системные колонки 'unnamed:' от pandas
                original_columns = list(df.columns)
                df = df.loc[:, ~df.columns.str.startswith('unnamed:')]
                # Проверяем, остались ли колонки
                if df.empty:
                    # print(f"    No valid columns left after removing 'unnamed:' for sheet '{sheet_name}'. Skipping.") # Убрал вывод
                     continue
                headers = list(df.columns)
                # print(f"    Using headers: {headers}") # Убрал вывод

            except Exception as e:
                sys.stderr.write(f"  ❌ ERROR reading/processing sheet '{sheet_name}' in '{document_name}': {e}\n")
                traceback.print_exc()
                continue # Переходим к следующему листу

            # --- Обработка строк ---
            # Итерируемся по строкам DataFrame
            for index, row in df.iterrows():
                # Создаем словарь строки, где ключ - заголовок, значение - текст ячейки (очищенный)
                # Включаем только непустые ячейки
                row_dict_cleaned = {
                    str(k): clean_text(str(v))
                    for k, v in row.to_dict().items()
                    if str(v).strip() # Проверяем, что значение не пустое *до* очистки clean_text
                }

                # Если строка оказалась пустой после фильтрации, пропускаем её
                if not row_dict_cleaned:
                    continue

                # Отдаем каждую непустую строку как отдельный блок
                source_info = {
                    "document_name": document_name,
                    "sheet_name": sheet_name,
                    # Реальный номер строки в Excel: index из df + номер строки заголовка + 1 (т.к. index с 0) + 1 (т.к. Excel с 1)
                    "row_index_excel": index + header_row_index + 1,
                    "headers": headers, # Передаем заголовки таблицы/листа
                    "document_hyperlinks": [] # Ссылки будут извлечены из текста при обработке метаданных
                }
                yield RawContentBlock(type='excel_row', content=row_dict_cleaned, source_info=source_info)

    except ImportError as e:
         sys.stderr.write(f"❌ CRITICAL Excel Error: Missing library for '{xlsx_path}'. Install 'openpyxl' (for .xlsx) or 'xlrd' (for .xls). Error: {e}\n")
    except Exception as e:
        sys.stderr.write(f"❌ CRITICAL Excel Error processing '{document_name}': {e}\n")
        traceback.print_exc()
    # print(f"✅ Finished processing Excel: {document_name}") # Убрал вывод

# --- Главная функция-диспетчер ---
def parse_document(file_path: str) -> Generator[RawContentBlock, None, None]:
    """
    Выбирает нужный парсер в зависимости от расширения файла.
    Возвращает генератор RawContentBlock.
    """
    extension = file_path.split(".")[-1].lower()
    document_name = os.path.basename(file_path)
    # print(f"🚀 Starting parsing for: {document_name} ({extension.upper()})") # Убрал вывод

    if extension == "pdf":
        yield from parse_pdf(file_path)
    elif extension == "docx":
        yield from parse_docx(file_path)
    elif extension in ["xlsx", "xls"]: # Добавили поддержку xls (требует xlrd)
        yield from parse_excel(file_path)
    else:
        sys.stderr.write(f"⚠️ Unsupported file type skipped: {document_name}\n")
        return # Возвращаем пустой генератор (или можно 'yield from []')

# --- END OF FILE document_parser.py ---