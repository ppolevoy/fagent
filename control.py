from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AbstractController(ABC):
    """
    Абстрактный базовый класс для всех контроллеров управления.

    Обязательные методы:
    - get_name(): возвращает уникальное имя контроллера
    - handle_action(): обработка POST запросов

    Опциональные методы:
    - handle_get(): обработка GET запросов (если контроллер поддерживает)
    """

    @abstractmethod
    def get_name(self) -> str:
        """Возвращает уникальное имя контроллера."""
        pass

    @abstractmethod
    def handle_action(self, action_path: List[str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает POST запросы (действия).

        Args:
            action_path: Параметры из URL после /api/v1/{controller_name}/
                        Например: ['backends', 'myapp', 'servers', 'web01', 'action']
            body: Тело POST запроса, например {'action': 'drain'}

        Returns:
            Dict[str, Any]: Результат в формате:
                {
                    'success': bool,
                    'status_code': int,
                    'data': Any,
                    'error': str (опционально)
                }
        """
        pass

    def handle_get(self, path_parts: List[str], query_params: Dict[str, str]) -> Dict[str, Any]:
        """
        Обрабатывает GET запросы (опциональный метод).

        Контроллеры, не реализующие этот метод, не будут обрабатывать GET запросы.

        Args:
            path_parts: Параметры из URL после /api/v1/{controller_name}/
                       Например: ['backends', 'myapp', 'servers']
            query_params: Query параметры из URL

        Returns:
            Dict[str, Any]: Результат в формате:
                {
                    'success': bool,
                    'status_code': int,
                    'data': Any,
                    'error': str (опционально)
                }
        """
        _ = path_parts  # Используется в переопределенных методах
        _ = query_params  # Используется в переопределенных методах
        raise NotImplementedError(f"Controller {self.get_name()} does not support GET requests")