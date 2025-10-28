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

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )    

    # Пути для SVC-плагина
    SVC_APP_ROOT = Path(os.getenv("SVC_APP_ROOT", "/site/app"))
    SVC_HTPDOC_ROOT = Path(os.getenv("SVC_HTPDOC_ROOT", "/site/share/htdoc"))

    SUPPORTED_ARTIFACT_EXTENSIONS = os.getenv(
        "SUPPORTED_ARTIFACT_EXTENSIONS", 
        "jar,war"
    ).split(',')    

    # Настройки безопасности
    SECURITY_ENABLED = os.getenv("AGENT_SECURITY_ENABLED", "false").lower() == "true"
    AUTH_TOKEN = os.getenv("AGENT_AUTH_TOKEN", "default-please-change-me")

    # Настройки HAProxy
    HAPROXY_SOCKET_PATH = os.getenv("HAPROXY_SOCKET_PATH", "/var/run/haproxy.sock")