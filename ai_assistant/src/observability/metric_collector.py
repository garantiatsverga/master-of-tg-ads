import sys
from pathlib import Path
from typing import Dict, Any
from prometheus_client import Counter, Histogram
import time
import threading

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from colordebug import info, error, warning
from ai_assistant.src.observability.logging_setup import log_performance_metrics

class MetricsCollector:
    """Сбор метрик работы ассистента с потокобезопасностью"""
    
    def __init__(self):
        # Prometheus метрики
        self.request_counter = Counter(
            'assistant_requests_total',
            'Общее количество запросов'
        )
        self.response_time = Histogram(
            'assistant_response_seconds',
            'Время ответа'
        )

        # Локальные метрики с блокировкой для потокобезопасности
        self._lock = threading.Lock()  # Мьютекс для синхронизации
        self._local = {
            'total_queries': 0,
            'successful_responses': 0,
            'total_time': 0.0,
            'intent_distribution': {}
        }
        info("Инициализирован с потокобезопасностью", exp=True)

    def log_query(self, question: str, intent: str,
                 response_time: float, success: bool = True) -> None:
        """
        Логирование метрик запроса с потокобезопасностью
        
        Args:
            question (str): Текст вопроса
            intent (str): Намерение пользователя
            response_time (float): Время ответа в секундах
            success (bool): Успешность ответа
        
        Заметка:
            Отрицательное время ответа автоматически обнуляется
        """
        # Обнуляем отрицательное время
        if response_time < 0:
            response_time = 0.0
            error("Обнаружено отрицательное время ответа, исправлено на 0", exp=True)
        
        # Инкремент Prometheus-метрик
        try:
            self.request_counter.inc()
            self.response_time.observe(response_time)
        except Exception as e:
            error(f"Ошибка при обновлении Prometheus-метрик: {e}", exp=True)

        # Потокобезопасное обновление локальных метрик
        with self._lock:
            self._local['total_queries'] += 1
            if success:
                self._local['successful_responses'] += 1
            self._local['total_time'] += response_time
            self._local['intent_distribution'][intent] = \
                self._local['intent_distribution'].get(intent, 0) + 1
        
        info(f"Запрос '{question[:50]}...' залогирован", exp=True)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Получение текущих метрик
        
        Returns:
            Dict[str, Any]: Словарь с метриками
        
        Note:
            Гарантирует потокобезопасное чтение метрик
        """
        # Потокобезопасное чтение метрик
        with self._lock:
            total_queries = self._local['total_queries']
            successful_responses = self._local['successful_responses']
            total_time = self._local['total_time']
            intent_distribution = self._local['intent_distribution'].copy()  # Копируем для безопасности
        
        # Вычисляем среднее время
        if total_queries > 0:
            avg_time = total_time / total_queries
        else:
            avg_time = 0.0
            warning("Нет запросов для вычисления среднего времени", exp=True)

        metrics_dict = {
            'total_queries': total_queries,
            'successful_responses': successful_responses,
            'avg_response_time': round(avg_time, 3),
            'total_response_time': round(total_time, 3),
            'intent_distribution': intent_distribution,
            'success_rate': (successful_responses / total_queries * 100) if total_queries > 0 else 0.0
        }

        # Логируем полученные метрики через logging_setup
        try:
            log_performance_metrics(metrics_dict)
            info("Метрики собраны и залогированы", exp=True)
        except Exception as e:
            error(f"Ошибка логирования метрик: {e}", exp=True)

        return metrics_dict

    def reset_metrics(self) -> None:
        """
        Сброс всех метрик
        
        Note:
            Потокобезопасный сброс метрик
        """
        with self._lock:
            self._local = {
                'total_queries': 0,
                'successful_responses': 0,
                'total_time': 0.0,
                'intent_distribution': {}
            }
        
        # Сброс Prometheus-метрик не поддерживается напрямую
        info("Метрики сброшены", exp=True)

# Пример использования
if __name__ == "__main__":
    collector = MetricsCollector()
    
    # Имитация многопоточного использования
    import random
    import concurrent.futures
    
    def simulate_request(request_id: int):
        """Имитация запроса"""
        intents = ["banner_gen", "text_gen", "compliance_check"]
        intent = random.choice(intents)
        resp_time = random.uniform(0.1, 2.0)
        success = random.choice([True, False])
        collector.log_query(f"Вопрос {request_id}", intent, resp_time, success)
        return f"Запрос {request_id} завершен"
    
    # 10 запросов в пуле потоков
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(simulate_request, i) for i in range(10)]
        for future in concurrent.futures.as_completed(futures):
            print(future.result())
    
    # Получение итоговых метрик
    metrics = collector.get_metrics()
    
    print("\n" + "_"*50)
    print("Итоговые метрики:")
    print("_"*50)
    for key, value in metrics.items():
        if key == 'intent_distribution':
            print(f"\nРаспределение интентов:")
            for intent, count in value.items():
                print(f"  {intent}: {count}")
        else:
            print(f"{key}: {value}")
    
    # Тест с отрицательным временем
    print("\n" + "_"*50)
    print("ТЕСТ: Запрос с отрицательным временем")
    print("_"*50)
    collector.log_query("Тестовый запрос", "test", -1.5, True)
    test_metrics = collector.get_metrics()
    print(f"Общее время после отрицательного: {test_metrics['total_response_time']}")