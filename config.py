import os
from pathlib import Path

class Config:
    """Класс для хранения конфигурации агента."""
    
    # Настройки сервера
    SERVER_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("AGENT_PORT", 11011))

    # Настройки обнаружения
    DISCOVERY_INTERVAL_SECONDS = int(os.getenv("DISCOVERY_INTERVAL", 60))
    PLUGINS_DIR = Path(__file__).parent / "plugins"

    # Пути для SVC-плагина
    SVC_APP_ROOT = Path(os.getenv("SVC_APP_ROOT", "/site/app"))
    SVC_HTPDOC_ROOT = Path(os.getenv("SVC_HTPDOC_ROOT", "/site/share/htdoc"))