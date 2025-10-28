import sys
import signal
import logging
import socket
import platform
import time
from typing import Optional

from discovery import DiscoveryManager
from server import run_server
from config import Config

def setup_logging() -> None:
    """Настройка системы логирования"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=Config.LOG_FORMAT
    )
    
    # Устанавливаем уровень для конкретных логгеров
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))

def update_data_periodically(discovery_manager: DiscoveryManager):
    """Фоновая задача для периодического обновления данных."""
    while True:
        logging.info("Starting application discovery cycle...")
        try:
            apps = discovery_manager.run_discovery()
            logging.info(f"Discovery cycle completed. Found {len(apps)} applications.")
        except Exception as e:
            logging.error(f"Error during discovery cycle: {e}")
        
        time.sleep(Config.DISCOVERY_INTERVAL_SECONDS)

def initialize_discovery_manager() -> Optional[DiscoveryManager]:
    """
    Инициализация менеджера обнаружения.

    Returns:
        Optional[DiscoveryManager]: Экземпляр менеджера или None при ошибке
    """
    setup_logging()
    logger = logging.getLogger(__name__)


    try:
        logger.info("Initializing discovery manager...")
        manager = DiscoveryManager()
        
        if not manager.discoverers:
            logger.warning("No detection plugins loaded!")
            return None
        
        logger.info(f"Plugins loaded: {len(manager.discoverers)}")
        for discoverer in manager.discoverers:
            logger.info(f"  - {type(discoverer).__name__}")
        
        # Пробный запуск обнаружения
        logger.info("Выполнение пробного обнаружения...")
        apps = manager.run_discovery()
        logger.info(f"Trial discovery completed. Apps found: {len(apps)}")
        
        return manager
        
    except Exception as e:
        logger.error(f"Error initializing discovery manager: {e}", exc_info=True)
        return None
    
def setup_signal_handlers() -> None:
    """Настройка обработчиков сигналов для graceful shutdown"""
    logger = logging.getLogger(__name__)

    def signal_handler(signum, frame):
        """Обработчик сигналов SIGTERM и SIGINT"""
        signal_names = {
            signal.SIGTERM: "SIGTERM",
            signal.SIGINT: "SIGINT"
        }
        signal_name = signal_names.get(signum, f"Signal {signum}")

        logger.info(f"Received {signal_name}, beginning graceful shutdown...")

        # Останавливаем HTTP сервер
        if httpd_instance:
            logger.info("Stopping HTTP server...")
            try:
                httpd_instance.shutdown()
                logger.info("HTTP server stopped ✓")
            except Exception as e:
                logger.error(f"Error stopping the server: {e}")

        logger.info("The agent has been stopped successfully.")
        sys.exit(0)

    # Регистрируем обработчики
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.debug("Signal handlers are registered")    

def main():
    """Главная функция для запуска агента."""

    global httpd_instance
    httpd_instance = None

    setup_logging()
    logger = logging.getLogger(__name__)    
    
    try:

        # Настройка обработчиков сигналов
        setup_signal_handlers()

        logging.info("Starting Application Discovery Agent...")
    
        # 1. Инициализация менеджера обнаружения (он сам загрузит плагины)
        discovery_manager = initialize_discovery_manager()
        if not discovery_manager:
            logger.error("Failed to initialize discovery manager")
            return 1

        # 2. Запуск фонового потока для обновления данных
        # (В этой версии данные запрашиваются "на лету" в each API request,
        # но поток полезен для периодических проверок или кеширования в будущем)
        # update_thread = threading.Thread(target=update_data_periodically, args=(discovery_manager,), daemon=True)
        # update_thread.start()

        # Запуск HTTP сервера
        logger.info("=" * 60)
        logger.info(f"Starting HTTP server on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
        logger.info("=" * 60)

        try:
            httpd_instance = run_server(discovery_manager)
            httpd_instance.serve_forever()

        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(
                    f"Port {Config.SERVER_PORT} is already in use. "
                    "Change SERVER_PORT in the configuration."
                )
            else:
                logger.error(f"Error starting server: {e}")
                return 1
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
        return 0
    
    except Exception as e:
        logging.error(f"Server failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)