#!/usr/bin/env python3
import sys
import signal
import logging
import threading
from typing import Optional

from discovery import DiscoveryManager
from discovery_scheduler import DiscoveryScheduler
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

        return manager
        
    except Exception as e:
        logger.error(f"Error initializing discovery manager: {e}", exc_info=True)
        return None
    
def setup_signal_handlers() -> None:
    """Настройка обработчиков сигналов для graceful shutdown"""
    logger = logging.getLogger(__name__)

    def signal_handler(*_):
        """Обработчик сигнала SIGTERM"""
        logger.info(f"Received SIGTERM, beginning graceful shutdown...")

        # Останавливаем DiscoveryScheduler
        if discovery_scheduler_instance:
            logger.info("Stopping DiscoveryScheduler...")
            try:
                discovery_scheduler_instance.stop()
                logger.info("DiscoveryScheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping DiscoveryScheduler: {e}")

        # Останавливаем HTTP сервер из отдельного потока
        if httpd_instance:
            logger.info("Stopping HTTP server...")
            try:
                # shutdown() нужно вызывать из отдельного потока
                shutdown_thread = threading.Thread(target=httpd_instance.shutdown)
                shutdown_thread.start()
                shutdown_thread.join(timeout=5)
                logger.info("HTTP server stopped")
            except Exception as e:
                logger.error(f"Error stopping the server: {e}")

        logger.info("The agent has been stopped successfully.")
        sys.exit(0)

    # Регистрируем только SIGTERM, SIGINT будет обработан через KeyboardInterrupt
    signal.signal(signal.SIGTERM, signal_handler)

    logger.debug("Signal handlers are registered")    

def main():
    """Главная функция для запуска агента."""

    global httpd_instance
    global discovery_scheduler_instance
    httpd_instance = None
    discovery_scheduler_instance = None

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

        # 2. Инициализация и запуск DiscoveryScheduler (фоновое сканирование с кэшированием)
        discovery_scheduler_instance = DiscoveryScheduler(discovery_manager)
        discovery_scheduler_instance.start()

        # Запуск HTTP сервера
        logger.info("=" * 60)
        logger.info(f"Starting HTTP server on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
        logger.info("=" * 60)

        try:
            httpd_instance = run_server(discovery_manager, discovery_scheduler=discovery_scheduler_instance)
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
        # Останавливаем DiscoveryScheduler при Ctrl+C
        if discovery_scheduler_instance:
            discovery_scheduler_instance.stop()
        return 0

    except Exception as e:
        logging.error(f"Server failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
