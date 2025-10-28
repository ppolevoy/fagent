import threading
import time
import logging
import socket

from discovery import DiscoveryManager
from server import run_server
from config import Config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

def main():
    """Главная функция для запуска агента."""
    logging.info("Starting Application Discovery Agent...")
    
    # 1. Инициализация менеджера обнаружения (он сам загрузит плагины)
    discovery_manager = DiscoveryManager()

    # 2. Запуск фонового потока для обновления данных
    # (В этой версии данные запрашиваются "на лету" в each API request,
    # но поток полезен для периодических проверок или кеширования в будущем)
    # update_thread = threading.Thread(target=update_data_periodically, args=(discovery_manager,), daemon=True)
    # update_thread.start()

    # 3. Запуск HTTP-сервера
    try:
        run_server(discovery_manager)
    except KeyboardInterrupt:
        logging.info("Agent stopped by user.")
    except Exception as e:
        logging.error(f"Server failed: {e}")

if __name__ == "__main__":
    main()