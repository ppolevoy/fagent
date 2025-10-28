# models.py
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ApplicationInfo:
    """Универсальная модель для информации о приложении."""
    name: str
    version: str
    status: str
    start_time: str = "Unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует объект в словарь."""
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "start_time": self.start_time,
            **self.metadata  # Добавляем все метаданные на верхний уровень
        }