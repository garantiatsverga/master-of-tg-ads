import unittest
import threading
import time
from ai_assistant.src.observability.metric_collector import MetricsCollector


class TestMetricsCollector(unittest.TestCase):
    """Тесты для класса MetricsCollector"""

    def setUp(self):
        """Инициализация перед каждым тестом"""
        self.collector = MetricsCollector()

    def test_initial_metrics(self):
        """Проверка начальных значений метрик"""
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 0)
        self.assertEqual(metrics['successful_responses'], 0)
        self.assertEqual(metrics['avg_response_time'], 0.0)
        self.assertEqual(metrics['total_response_time'], 0.0)
        self.assertEqual(metrics['intent_distribution'], {})
        self.assertEqual(metrics['success_rate'], 0.0)

    def test_log_query_success(self):
        """Проверка логирования успешного запроса"""
        self.collector.log_query("Test question", "test_intent", 1.5, True)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 1)
        self.assertEqual(metrics['successful_responses'], 1)
        self.assertEqual(metrics['avg_response_time'], 1.5)
        self.assertEqual(metrics['total_response_time'], 1.5)
        self.assertEqual(metrics['intent_distribution'], {"test_intent": 1})
        self.assertEqual(metrics['success_rate'], 100.0)

    def test_log_query_failure(self):
        """Проверка логирования неудачного запроса"""
        self.collector.log_query("Test question", "test_intent", 1.5, False)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 1)
        self.assertEqual(metrics['successful_responses'], 0)
        self.assertEqual(metrics['avg_response_time'], 1.5)
        self.assertEqual(metrics['total_response_time'], 1.5)
        self.assertEqual(metrics['intent_distribution'], {"test_intent": 1})
        self.assertEqual(metrics['success_rate'], 0.0)

    def test_negative_response_time(self):
        """Проверка обработки отрицательного времени ответа"""
        self.collector.log_query("Test question", "test_intent", -1.5, True)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 1)
        self.assertEqual(metrics['successful_responses'], 1)
        self.assertEqual(metrics['avg_response_time'], 0.0)
        self.assertEqual(metrics['total_response_time'], 0.0)
        self.assertEqual(metrics['intent_distribution'], {"test_intent": 1})
        self.assertEqual(metrics['success_rate'], 100.0)

    def test_multiple_queries(self):
        """Проверка логирования нескольких запросов"""
        self.collector.log_query("Question 1", "intent1", 1.0, True)
        self.collector.log_query("Question 2", "intent2", 2.0, True)
        self.collector.log_query("Question 3", "intent1", 3.0, False)
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 3)
        self.assertEqual(metrics['successful_responses'], 2)
        self.assertEqual(metrics['avg_response_time'], 2.0)
        self.assertEqual(metrics['total_response_time'], 6.0)
        self.assertEqual(metrics['intent_distribution'], {"intent1": 2, "intent2": 1})
        self.assertEqual(metrics['success_rate'], 100.0 * 2 / 3)

    def test_thread_safety(self):
        """Проверка потокобезопасности"""
        def log_requests(start, end):
            for i in range(start, end):
                self.collector.log_query(f"Question {i}", "test_intent", 1.0, True)

        threads = []
        for i in range(0, 100, 10):
            thread = threading.Thread(target=log_requests, args=(i, i + 10))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        metrics = self.collector.get_metrics()
        self.assertEqual(metrics['total_queries'], 100)
        self.assertEqual(metrics['successful_responses'], 100)
        self.assertEqual(metrics['avg_response_time'], 1.0)
        self.assertEqual(metrics['total_response_time'], 100.0)
        self.assertEqual(metrics['intent_distribution'], {"test_intent": 100})
        self.assertEqual(metrics['success_rate'], 100.0)

    def test_reset_metrics(self):
        """Проверка сброса метрик"""
        self.collector.log_query("Question 1", "intent1", 1.0, True)
        self.collector.log_query("Question 2", "intent2", 2.0, True)
        metrics_before = self.collector.get_metrics()
        self.assertEqual(metrics_before['total_queries'], 2)

        self.collector.reset_metrics()
        metrics_after = self.collector.get_metrics()
        self.assertEqual(metrics_after['total_queries'], 0)
        self.assertEqual(metrics_after['successful_responses'], 0)
        self.assertEqual(metrics_after['avg_response_time'], 0.0)
        self.assertEqual(metrics_after['total_response_time'], 0.0)
        self.assertEqual(metrics_after['intent_distribution'], {})
        self.assertEqual(metrics_after['success_rate'], 0.0)


if __name__ == '__main__':
    unittest.main()