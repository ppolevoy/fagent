# server.py
import json
import socket
import urllib.parse
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Dict, Any
from datetime import datetime, timedelta

from models import ApplicationInfo
from discovery import DiscoveryManager
from config import Config
from control_manager import ControlManager

logger = logging.getLogger(__name__)

def get_hostname() -> str:
    """Получает имя хоста."""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_ip_address() -> str:
    """Получает IP-адрес сервера."""
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except Exception:
        return "0.0.0.0"


class AgentRequestHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов."""

    # Внедряем зависимость через атрибут класса (простой способ для примера)
    discovery_manager: DiscoveryManager = None
    control_manager: ControlManager = None

    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def _send_error_response(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))

    def _get_url_path_parts(self) -> List[str]:
        """Разбирает URL путь на части."""
        return [part for part in urllib.parse.urlparse(self.path).path.split('/') if part]

    def _format_docker_apps(self, apps: List[ApplicationInfo]) -> List[Dict[str, Any]]:
        """Форматирование Docker приложений для JSON ответа."""
        result = []
        for app in apps:
            docker_app = {
                "container_id": app.metadata.get("container_id", ""),
                "container_name": app.metadata.get("container_name", app.name),
                "image": app.metadata.get("image", ""),
                "tag": app.metadata.get("tag", ""),
                "ip": app.metadata.get("ip", ""),
                "port": app.metadata.get("port"),
                "compose_project_dir": app.metadata.get("compose_project_dir"),
                "status": app.status,
                "pid": app.metadata.get("pid"),
                "start_time": app.start_time
            }
            # Убираем None значения
            result.append({k: v for k, v in docker_app.items() if v is not None})
        return result

    def _format_svc_apps(self, apps: List[ApplicationInfo]) -> List[Dict[str, Any]]:
        """Форматирование SVC приложений для JSON ответа."""
        result = []
        for app in apps:
            svc_app = {
                "name": app.name,
                "version": app.version,
                "status": app.status,
                "start_time": app.start_time,
                "pid": app.metadata.get("pid"),
                "port": app.metadata.get("port"),
                "log_path": app.metadata.get("log_path"),
                "distr_path": app.metadata.get("distr_path"),
                "artifact_size_bytes": app.metadata.get("artifact_size_bytes"),
                "artifact_size_mb": app.metadata.get("artifact_size_mb"),
                "artifact_type": app.metadata.get("artifact_type"),
                "app_path": app.metadata.get("app_path")
            }
            # Убираем None значения
            result.append({k: v for k, v in svc_app.items() if v is not None})
        return result

    def do_GET(self):
        parts = self._get_url_path_parts()

        if self.path == "/ping":
            self._set_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        # Обработка запроса списка приложений
        # Поддерживаем два варианта: /app (старый) и /api/v1/apps (новый, множественное число)
        elif self.path == "/app" or self.path == "/api/v1/apps":
            apps = self.discovery_manager.run_discovery()

            # Формируем метку времени в формате YYYYMMDD_HHMMSS с добавлением 4 часов
            last_update = (datetime.now() + timedelta(hours=7)).strftime("%Y%m%d_%H%M%S")

            # Группируем приложения по источнику
            docker_apps = []
            svc_apps = []

            for app in apps:
                source = app.metadata.get("source", "unknown")
                if source == "docker":
                    docker_apps.append(app)
                elif source == "svc":
                    svc_apps.append(app)
                # Если source не указан (старые плагины), считаем что это SVC
                elif source == "unknown":
                    svc_apps.append(app)

            # Формируем ответ с разделением по источникам
            response_data = {
                "server": {
                    "name": get_hostname(),
                    "ip": get_ip_address()
                }
            }

            # Добавляем docker-app секцию только если есть Docker приложения
            if docker_apps:
                response_data["server"]["docker-app"] = {
                    "applications": self._format_docker_apps(docker_apps),
                    "count": len(docker_apps),
                    "last_update": last_update
                }

            # Всегда добавляем site-app секцию (SVC приложения)
            response_data["server"]["site-app"] = {
                "applications": self._format_svc_apps(svc_apps),
                "count": len(svc_apps),
                "last_update": last_update
            }

            self._set_headers()
            self.wfile.write(json.dumps(response_data, indent=4).encode("utf-8"))
            return

        # Обработка API GET запросов для контроллеров
        # URL: /api/v1/{controller_name}/...
        elif len(parts) >= 3 and parts[0:2] == ['api', 'v1']:
            controller_name = parts[2]

            # Получаем контроллер
            controller = self.control_manager.get_controller(controller_name)

            if not controller:
                # Контроллер не найден - возвращаем детальную ошибку
                self._send_error_response(404, f"Controller '{controller_name}' not found")
                return
            else:
                # Проверяем, поддерживает ли контроллер GET запросы
                if hasattr(controller, 'handle_get'):
                    try:
                        # Извлекаем путь после /api/v1/{controller_name}/
                        resource_path = parts[3:]

                        # Парсим query параметры
                        parsed_url = urllib.parse.urlparse(self.path)
                        query_params = dict(urllib.parse.parse_qsl(parsed_url.query))

                        # Вызываем handle_get контроллера
                        result = controller.handle_get(resource_path, query_params)

                        # Отправляем ответ
                        status_code = result.get('status_code', 200)
                        self._set_headers(status_code)
                        self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))
                        return

                    except Exception as e:
                        logger.error(f"Ошибка обработки GET запроса к контроллеру '{controller_name}': {e}", exc_info=True)
                        self._send_error_response(500, f"Internal error: {str(e)}")
                        return
                else:
                    # Контроллер не поддерживает GET
                    self._send_error_response(405, f"Controller '{controller_name}' does not support GET requests")
                    return

        # 404 для всех остальных путей
        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))


    def do_POST(self):
        parts = self._get_url_path_parts()

        # Проверяем минимальную длину пути
        if len(parts) < 3:
            self._send_error_response(400, "Invalid request path")
            return

        # Проверяем, что это API запрос
        if parts[0:2] != ['api', 'v1']:
            self._send_error_response(404, "Not Found")
            return

        controller_name = parts[2]

        # Вариант 1: Новый API - прямой доступ /api/v1/haproxy/...
        # Вариант 2: Старый API - /api/v1/control/{controller_name}/...
        if controller_name == 'control' and len(parts) >= 4:
            # Старый формат: /api/v1/control/{controller_name}/...
            controller_name = parts[3]
            action_path = parts[4:]
        else:
            # Новый формат: /api/v1/{controller_name}/...
            action_path = parts[3:]

        # Получаем контроллер
        controller = self.control_manager.get_controller(controller_name)

        if not controller:
            self._send_error_response(404, f"Controller '{controller_name}' not found")
            return

        try:
            # Читаем и парсим тело запроса
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                body = json.loads(post_data.decode('utf-8'))
            else:
                body = {}

            # Вызываем handle_action контроллера
            result = controller.handle_action(action_path, body)

            # Отправляем ответ
            status_code = result.get('status_code', 200)
            self._set_headers(status_code)
            self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            self._send_error_response(400, f"Invalid JSON: {str(e)}")

        except Exception as e:
            logger.error(f"Ошибка обработки POST запроса: {e}", exc_info=True)
            self._send_error_response(500, f"Internal error: {str(e)}")    

    def log_message(self, format, *args):
        """Отключаем стандартный логгинг HTTP-сервера, чтобы управлять им централизованно."""
        pass

def run_server(discovery_manager: DiscoveryManager, control_manager: ControlManager = None):
    """
    Создает HTTP-сервер и возвращает его экземпляр.

    Args:
        discovery_manager: Менеджер обнаружения приложений
        control_manager: Менеджер контроллеров (опционально)
    """
    server_address = (Config.SERVER_HOST, Config.SERVER_PORT)

    # Внедряем менеджеры в обработчик
    AgentRequestHandler.discovery_manager = discovery_manager

    # Инициализируем control_manager если не передан
    if control_manager is None:
        logger.info("Инициализация ControlManager")
        control_manager = ControlManager()

    AgentRequestHandler.control_manager = control_manager

    # Создаем сервер
    httpd = HTTPServer(server_address, AgentRequestHandler)
    logger.info(f"HTTP сервер создан на {Config.SERVER_HOST}:{Config.SERVER_PORT}")

    return httpd