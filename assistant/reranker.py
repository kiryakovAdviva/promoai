# --- START OF FILE reranker.py ---

import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from sentence_transformers import CrossEncoder
import sys
import os
from pathlib import Path
from .cache import init_reranker_cache

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", max_length: int = 512):
        """
        Инициализация reranker'а с cross-encoder моделью.
        
        Args:
            model_name: Название модели для переранжирования
            max_length: Максимальная длина текста для reranking'а
        """
        try:
            print(f"🔄 Загрузка модели reranker: {model_name}...")
            self.model = CrossEncoder(model_name)
            self.cache = init_reranker_cache()
            self.max_length = max_length
            print("✅ Модель reranker успешно загружена")
        except Exception as e:
            print(f"❌ Ошибка при загрузке модели reranker: {e}")
            self.model = None
            self.cache = None

    def _truncate_text(self, text: str) -> str:
        """
        Обрезка текста до максимальной длины.
        
        Args:
            text: Исходный текст
            
        Returns:
            str: Обрезанный текст
        """
        if not text:
            return ""
            
        # Разбиваем на слова
        words = text.split()
        
        # Если текст короче максимальной длины, возвращаем как есть
        if len(words) <= self.max_length:
            return text
            
        # Берем первые max_length слов
        truncated = " ".join(words[:self.max_length])
        
        # Добавляем многоточие, если текст был обрезан
        if len(words) > self.max_length:
            truncated += "..."
            
        return truncated

    def rerank(self, 
               query: str, 
               documents: List[Dict[str, Any]], 
               top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """
        Переранжирование документов относительно запроса.
        
        Args:
            query: Текстовый запрос
            documents: Список документов для переранжирования
            top_k: Количество возвращаемых результатов
            
        Returns:
            list: Список кортежей [(document, score), ...]
        """
        if not self.model or not documents:
            return [(doc, 0.0) for doc in documents[:top_k]]
            
        try:
            # Проверяем кэш
            if self.cache:
                cached_result = self.cache.get(query, documents)
                if cached_result is not None:
                    print("📦 Используем кэшированный результат reranking'а")
                    return cached_result
            
            # Подготовка пар запрос-документ для оценки
            # Обрезаем текст документов до максимальной длины
            pairs = [(query, self._truncate_text(doc.get('text', ''))) for doc in documents]
            
            # Получение оценок релевантности
            scores = self.model.predict(pairs)
            
            # Сортировка документов по оценкам
            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            result = scored_docs[:top_k]
            
            # Сохраняем в кэш
            if self.cache:
                self.cache.set(query, documents, result)
                
            return result
            
        except Exception as e:
            print(f"❌ Ошибка при переранжировании: {e}")
            return [(doc, 0.0) for doc in documents[:top_k]]

    def rerank_with_weights(self,
                          query: str,
                          documents: List[Dict[str, Any]],
                          top_k: int = 5,
                          semantic_weight: float = 0.7,
                          rerank_weight: float = 0.3) -> List[Tuple[Dict[str, Any], float]]:
        """
        Переранжирование с учетом весов семантического поиска и reranking'а.
        
        Args:
            query: Текстовый запрос
            documents: Список документов с их семантическими скорами
            top_k: Количество возвращаемых результатов
            semantic_weight: Вес семантического поиска
            rerank_weight: Вес reranking'а
            
        Returns:
            list: Список кортежей [(document, final_score), ...]
        """
        if not self.model or not documents:
            return documents[:top_k]
            
        try:
            # Проверяем кэш
            if self.cache:
                cached_result = self.cache.get(query, documents)
                if cached_result is not None:
                    print("📦 Используем кэшированный результат взвешенного reranking'а")
                    return cached_result
            
            # Получаем reranking оценки
            reranked_docs = self.rerank(query, [doc for doc, _ in documents])
            
            # Комбинируем оценки
            final_scores = []
            for (doc, semantic_score), (_, rerank_score) in zip(documents, reranked_docs):
                final_score = (semantic_score * semantic_weight + 
                             rerank_score * rerank_weight)
                final_scores.append((doc, final_score))
                
            # Сортировка по финальным оценкам
            final_scores.sort(key=lambda x: x[1], reverse=True)
            
            result = final_scores[:top_k]
            
            # Сохраняем в кэш
            if self.cache:
                self.cache.set(query, documents, result)
                
            return result
            
        except Exception as e:
            print(f"❌ Ошибка при взвешенном переранжировании: {e}")
            return documents[:top_k]

# Создаем глобальный экземпляр reranker'а
reranker = None

def init_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", max_length: int = 512) -> Reranker:
    """
    Инициализация глобального reranker'а.
    """
    global reranker
    if reranker is None:
        reranker = Reranker(model_name, max_length)
    return reranker

# --- END OF FILE reranker.py --- 