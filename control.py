from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AbstractController(ABC):
    """Абстрактный базовый класс для всех плагинов управления."""

    @abstractmethod
    def get_name(self) -> str:
        """Возвращает уникальное имя контроллера."""
        pass

    @abstractmethod
    def handle_action(self, action_path: List[str], body: Dict[str, Any]) -> Any:
        """
        Основной метод для выполнения действия.
        
        Args:
            action_path: Параметры из URL, например ['backends', 'myapp', 'servers', 'web01']
            body: Тело запроса, например {'action': 'drain'}
        
        Returns:
            Результат выполнения действия.
        """
        pass