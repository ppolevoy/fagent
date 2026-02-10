# discovery_scheduler.py
"""
DiscoveryScheduler — планировщик фонового сканирования с кэшированием.

Паттерны:
- Background Refresh: периодическое обновление в фоновом потоке
- Stale-While-Revalidate: отдаём данные из кэша, пока обновляем в фоне
- Graceful Degradation: при ошибке сканирования — отдаём последние успешные данные

Использование:
    from discovery_scheduler import DiscoveryScheduler
    from discovery import DiscoveryManager

    dm = DiscoveryManager()
    scheduler = DiscoveryScheduler(dm)
    scheduler.start()  # Выполнит первичный скан + запустит фоновый поток

    # В API:
    apps = scheduler.get_apps()
    cache_info = scheduler.get_cache_info()

    # При shutdown:
    scheduler.stop()
"""
import threading
import time
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from models import ApplicationInfo
from config import Config

if TYPE_CHECKING:
    from discovery import DiscoveryManager

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryCache:
    """
    Кэш результатов discovery.

    Хранит:
    - apps: текущий список приложений
    - last_scan: время последнего успешного сканирования
    - scan_duration_ms: время выполнения последнего сканирования
    - previous_state: {app_name: start_time} для детекции изменений
    - error: ошибка последнего сканирования (если была)
    """
    apps: List[ApplicationInfo] = field(default_factory=list)
    last_scan: Optional[datetime] = None
    scan_duration_ms: int = 0
    previous_state: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class DiscoveryScheduler:
    """
    Планировщик фонового сканирования приложений.

    Реализует паттерн Background Refresh:
    - Периодически выполняет discovery в фоновом потоке
    - Кэширует результаты для быстрого доступа через API
    - Детектирует изменения (перезапуски приложений)
    - Обеспечивает graceful degradation при ошибках

    Thread-safety:
    - Все операции с кэшем защищены RLock
    - get_apps() возвращает копию данных, не ссылку
    """

    def __init__(self, discovery_manager: "DiscoveryManager") -> None:
        """
        Args:
            discovery_manager: Экземпляр DiscoveryManager для выполнения сканирования
        """
        self.discovery_manager = discovery_manager

        # Конфигурация
        self.enabled = Config.DISCOVERY_CACHE_ENABLED
        self.refresh_interval = Config.DISCOVERY_REFRESH_INTERVAL
        self.stale_threshold = Config.DISCOVERY_STALE_THRESHOLD
        self.max_stale = Config.DISCOVERY_MAX_STALE
        self.jitter = Config.DISCOVERY_JITTER

        # Состояние
        self._cache = DiscoveryCache()
        self._lock = threading.RLock()
        self._scan_lock = threading.Lock()  # Защита от параллельных scan
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._error_count = 0

        logger.info(
            f"DiscoveryScheduler инициализирован: "
            f"enabled={self.enabled}, interval={self.refresh_interval}s, "
            f"stale_threshold={self.stale_threshold}s, max_stale={self.max_stale}s"
        )

    def start(self) -> None:
        """
        Запуск планировщика.

        1. Выполняет первичный синхронный скан (блокирует до завершения)
        2. Запускает фоновый поток для периодического обновления
        """
        if not self.enabled:
            logger.info("DiscoveryScheduler отключен (DISCOVERY_CACHE_ENABLED=false)")
            return

        if self._running:
            logger.warning("DiscoveryScheduler уже запущен")
            return

        logger.info("Запуск DiscoveryScheduler...")

        # Первичный синхронный скан
        self._scan()

        # Запуск фонового потока
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="DiscoveryScheduler",
            daemon=True
        )
        self._thread.start()

        logger.info("DiscoveryScheduler запущен")

    def stop(self) -> None:
        """
        Остановка планировщика.

        Выполняет graceful shutdown фонового потока.
        """
        if not self._running:
            return

        logger.info("Остановка DiscoveryScheduler...")
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("DiscoveryScheduler не остановился за 5 секунд")

        logger.info("DiscoveryScheduler остановлен")

    def get_apps(self) -> List[ApplicationInfo]:
        """
        Получить кэшированный список приложений.

        Returns:
            Копия списка приложений (не ссылка на оригинал)
        """
        # Если кэширование отключено — выполняем discovery напрямую
        if not self.enabled:
            return self.discovery_manager.run_discovery()

        with self._lock:
            # Возвращаем копию, чтобы избежать race conditions
            return list(self._cache.apps)

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Получить информацию о состоянии кэша.

        Returns:
            Dict с полями:
            - status: "fresh" | "valid" | "stale" | "expired"
            - age_seconds: возраст кэша в секундах
            - last_refresh: ISO timestamp последнего обновления
            - next_refresh_seconds: секунд до следующего обновления
            - scan_duration_ms: время последнего сканирования
            - error: ошибка (если была)
            - enabled: включен ли кэш
        """
        if not self.enabled:
            return {
                "enabled": False,
                "status": "disabled"
            }

        with self._lock:
            age = self._cache_age()
            return {
                "enabled": True,
                "status": self._cache_status(age),
                "age_seconds": round(age, 1),
                "last_refresh": self._cache.last_scan.isoformat() if self._cache.last_scan else None,
                "next_refresh_seconds": max(0, round(self.refresh_interval - age, 1)),
                "scan_duration_ms": self._cache.scan_duration_ms,
                "error": self._cache.error
            }

    def force_refresh(self) -> None:
        """
        Принудительное обновление кэша с защитой от дублирования.

        Если сканирование уже выполняется, ожидает его завершения
        вместо запуска параллельного скана.
        """
        # Пытаемся захватить лок без блокировки
        acquired = self._scan_lock.acquire(blocking=False)
        if not acquired:
            # Сканирование уже идёт — просто ждём его завершения
            logger.debug("Сканирование уже выполняется, ожидаем...")
            with self._scan_lock:
                pass  # Ждём завершения текущего scan
            return

        try:
            logger.debug("Принудительное обновление кэша")
            self._scan()
        finally:
            self._scan_lock.release()

    def _run_loop(self) -> None:
        """
        Основной цикл фонового потока.

        Выполняет сканирование с заданным интервалом + jitter.
        При ошибках применяет exponential backoff.
        """
        while self._running:
            # Вычисляем время сна с jitter
            jitter_value = random.uniform(-self.jitter, self.jitter)
            sleep_time = self.refresh_interval * (1 + jitter_value)

            # Спим с проверкой флага _running каждую секунду
            for _ in range(int(sleep_time)):
                if not self._running:
                    return
                time.sleep(1)

            # Остаток времени
            remainder = sleep_time - int(sleep_time)
            if remainder > 0 and self._running:
                time.sleep(remainder)

            if not self._running:
                return

            # Выполняем сканирование
            try:
                self._scan()
                self._error_count = 0
            except Exception as e:
                self._error_count += 1
                logger.error(f"Ошибка фонового сканирования ({self._error_count}): {e}")

                # Exponential backoff при повторных ошибках
                if self._error_count > 3:
                    backoff = min(300, 2 ** self._error_count)
                    logger.warning(f"Применяется backoff: {backoff}s после {self._error_count} ошибок")
                    time.sleep(backoff)

    def _scan(self) -> None:
        """
        Выполнить сканирование и обновить кэш.

        При ошибке:
        - Логирует ошибку
        - Сохраняет её в кэш
        - НЕ очищает предыдущие данные (graceful degradation)
        """
        start_time = time.time()

        try:
            apps = self.discovery_manager.run_discovery()
            duration_ms = int((time.time() - start_time) * 1000)

            # Создаём новое состояние для детекции изменений
            current_state = {
                app.name: app.start_time
                for app in apps
            }

            with self._lock:
                # Собираем изменения БЕЗ логирования (под локом)
                changes = self._collect_changes(current_state)

                # Обновляем кэш
                self._cache.apps = apps
                self._cache.last_scan = datetime.now()
                self._cache.scan_duration_ms = duration_ms
                self._cache.previous_state = current_state
                self._cache.error = None

            # Логируем изменения ПОСЛЕ выхода из лока
            for change in changes:
                logger.info(change)

            logger.debug(f"Кэш обновлён: {len(apps)} приложений за {duration_ms}ms")

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Ошибка сканирования после {duration_ms}ms: {e}")

            with self._lock:
                # Сохраняем ошибку, но НЕ очищаем кэш (graceful degradation)
                self._cache.error = str(e)

            raise

    def _collect_changes(self, current_state: Dict[str, str]) -> List[str]:
        """
        Собирает сообщения об изменениях между сканированиями.

        Сравнивает start_time приложений и возвращает список сообщений.
        Логирование выполняется вызывающим кодом ВНЕ блокировки.

        Args:
            current_state: {app_name: start_time} из текущего сканирования

        Returns:
            List[str]: Список сообщений об изменениях
        """
        changes: List[str] = []

        if not self._cache.previous_state:
            return changes

        for name, start_time in current_state.items():
            prev_time = self._cache.previous_state.get(name)

            if prev_time and prev_time != start_time:
                changes.append(f"Обнаружен перезапуск приложения: {name} ({prev_time} → {start_time})")

        # Детектируем удалённые приложения
        for name in self._cache.previous_state:
            if name not in current_state:
                changes.append(f"Приложение исчезло: {name}")

        # Детектируем новые приложения
        for name in current_state:
            if name not in self._cache.previous_state:
                changes.append(f"Новое приложение: {name}")

        return changes

    def _cache_age(self) -> float:
        """
        Возраст кэша в секундах.

        Returns:
            Секунды с последнего успешного сканирования (или бесконечность если не было)
        """
        if self._cache.last_scan is None:
            return float('inf')
        return (datetime.now() - self._cache.last_scan).total_seconds()

    def _cache_status(self, age: float) -> str:
        """
        Определить статус кэша по возрасту.

        Args:
            age: возраст кэша в секундах

        Returns:
            - "fresh": данные актуальны (age < refresh_interval)
            - "valid": данные валидны (age < stale_threshold)
            - "stale": данные устаревают (age < max_stale)
            - "expired": данные слишком старые
        """
        if age < self.refresh_interval:
            return "fresh"
        elif age < self.stale_threshold:
            return "valid"
        elif age < self.max_stale:
            return "stale"
        else:
            return "expired"
