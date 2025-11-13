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

    # Множественные HAProxy инстансы (опционально)
    # Форматы:
    #   - Один адрес (создаст default инстанс):
    #     - Unix socket: "/var/run/haproxy.sock"
    #     - TCP IPv4: "ipv4@192.168.1.1:7777"
    #   - Несколько с именами (разделитель =):
    #     "prod=ipv4@192.168.1.1:7777,test=ipv4@192.168.1.2:7777"
    #     "prod=/var/run/haproxy1.sock,test=/var/run/haproxy2.sock"
    # Если не указано, используется HAPROXY_SOCKET_PATH как default инстанс
    HAPROXY_INSTANCES = os.getenv("HAPROXY_INSTANCES", 'ipv4@192.168.1.1:7777')

    # Таймаут для операций с HAProxy (секунды)
    HAPROXY_TIMEOUT = float(os.getenv("HAPROXY_TIMEOUT", "5.0"))

    # Docker Discovery Settings
    DOCKER_DISCOVERY_ENABLED = os.getenv("DOCKER_DISCOVERY_ENABLED", "true").lower() == "true"
    DOCKER_SOCKET_PATH = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
    DOCKER_REQUEST_TIMEOUT = int(os.getenv("DOCKER_REQUEST_TIMEOUT", "10"))

    # Eureka Discovery Settings
    EUREKA_DISCOVERY_ENABLED = os.getenv("EUREKA_DISCOVERY_ENABLED", "false").lower() == "true"
    EUREKA_HOST = os.getenv("EUREKA_HOST", "fdse.f.ftc.ru")
    EUREKA_PORT = int(os.getenv("EUREKA_PORT", "8761"))
    EUREKA_REQUEST_TIMEOUT = int(os.getenv("EUREKA_REQUEST_TIMEOUT", "10"))