from abc import ABC, abstractmethod
from typing import List, Optional
import importlib.util
import inspect
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass
from pathlib import Path

from models import ApplicationInfo
from config import Config
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginResult:
    """Результат выполнения одного плагина discovery."""
    plugin_name: str
    apps: List[ApplicationInfo]
    duration_ms: float
    success: bool
    error: Optional[str] = None


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
        self._lock = threading.Lock()  # Защита от race conditions при параллельных запросах
        self._load_plugins()

    def _run_plugin_with_timeout(self, discoverer: AbstractDiscoverer) -> PluginResult:
        """Запуск плагина с замером времени."""
        plugin_name = type(discoverer).__name__
        start_time = time.time()

        try:
            apps = discoverer.discover()
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Plugin {plugin_name} completed in {duration_ms:.0f}ms, found {len(apps)} apps")
            return PluginResult(plugin_name=plugin_name, apps=apps, duration_ms=duration_ms, success=True)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Plugin {plugin_name} failed after {duration_ms:.0f}ms: {e}")
            return PluginResult(plugin_name=plugin_name, apps=[], duration_ms=duration_ms, success=False, error=str(e))

    def _load_plugins(self):
        """Динамически загружает все плагины из директории plugins/."""
        logger.info(f"Loading plugins from: {Config.PLUGINS_DIR}")
        for file_path in Config.PLUGINS_DIR.glob("*_discoverer.py"):
            module_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Ищем классы, наследующиеся от AbstractDiscoverer
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, AbstractDiscoverer) and obj is not AbstractDiscoverer:
                            try:
                                # Пытаемся создать экземпляр плагина
                                instance = obj()
                                logger.info(f"  - Loaded discoverer: {name}")
                                self.discoverers.append(instance)
                            except Exception as e:
                                logger.warning(f"  - Failed to initialize discoverer {name}: {e}")
            except ImportError as e:
                logger.warning(f"  - Failed to import plugin {module_name}: {e}")
            except Exception as e:
                logger.error(f"  - Unexpected error loading plugin {module_name}: {e}")
    
    def _run_discovery_parallel(self) -> List[ApplicationInfo]:
        """Параллельное выполнение всех плагинов с таймаутами."""
        all_apps = []
        plugin_timeout = Config.DISCOVERY_PLUGIN_TIMEOUT_SECONDS
        total_timeout = Config.DISCOVERY_TOTAL_TIMEOUT_SECONDS
        workers = min(Config.DISCOVERY_PARALLEL_WORKERS, len(self.discoverers)) if self.discoverers else 1

        if not self.discoverers:
            return all_apps

        start_time = time.time()
        successful = []
        failed = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_plugin = {
                executor.submit(self._run_plugin_with_timeout, d): d
                for d in self.discoverers
            }

            try:
                for future in as_completed(future_to_plugin, timeout=total_timeout):
                    try:
                        # future уже завершена после as_completed(), timeout не нужен
                        result = future.result()
                        if result.success:
                            all_apps.extend(result.apps)
                            successful.append(f"{result.plugin_name}({len(result.apps)} apps, {result.duration_ms:.0f}ms)")
                        else:
                            failed.append(f"{result.plugin_name}({result.error})")
                    except Exception as e:
                        plugin = future_to_plugin[future]
                        plugin_name = type(plugin).__name__
                        failed.append(f"{plugin_name}({e})")
                        logger.error(f"Plugin {plugin_name} unexpected error: {e}")
            except FuturesTimeoutError:
                # Общий таймаут истёк - отменяем незавершённые задачи
                logger.warning(f"Total discovery timeout ({total_timeout}s) exceeded")
                for future, plugin in future_to_plugin.items():
                    if not future.done():
                        future.cancel()
                        plugin_name = type(plugin).__name__
                        failed.append(f"{plugin_name}(total_timeout)")

        total_duration = (time.time() - start_time) * 1000
        logger.info(f"Discovery completed in {total_duration:.0f}ms: OK=[{', '.join(successful)}] FAILED=[{', '.join(failed) if failed else 'none'}]")

        return all_apps

    def run_discovery(self) -> List[ApplicationInfo]:
        """Запускает обнаружение на всех плагинах параллельно."""
        with self._lock:
            return self._run_discovery_parallel()