from abc import ABC, abstractmethod
from typing import List
import importlib.util
import inspect
from pathlib import Path

from models import ApplicationInfo
from config import Config
import logging

logger = logging.getLogger(__name__)

class AbstractDiscoverer(ABC):
    """Абстрактный базовый класс для всех плагинов обнаружения."""

    @abstractmethod
    def discover(self) -> List[ApplicationInfo]:
        """
        Основной метод, который должен быть реализован в каждом плагине.
        Должен возвращать список обнаруженных приложений.
        """
        pass

class DiscoveryManager:
    """Менеджер, который загружает плагины и собирает с них данные."""

    def __init__(self):
        self.discoverers: List[AbstractDiscoverer] = []
        self._load_plugins()

    def _load_plugins(self):
        """Динамически загружает все плагины из директории plugins/."""
        logger.info(f"Loading plugins from: {Config.PLUGINS_DIR}")
        for file_path in Config.PLUGINS_DIR.glob("*_discoverer.py"):
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Ищем классы, наследующиеся от AbstractDiscoverer
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, AbstractDiscoverer) and obj is not AbstractDiscoverer:
                        logger.info(f"  - Loaded discoverer: {name}")
                        self.discoverers.append(obj())
    
    def run_discovery(self) -> List[ApplicationInfo]:
        """Запускает обнаружение на всех загруженных плагинах."""
        all_apps = []
        for discoverer in self.discoverers:
            try:
                apps = discoverer.discover()
                all_apps.extend(apps)
            except Exception as e:
                logger.info(f"Error running discoverer {type(discoverer).__name__}: {e}")
        
        return all_apps