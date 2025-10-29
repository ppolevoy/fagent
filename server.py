# server.py
import json
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List
from datetime import datetime, timedelta

from models import ApplicationInfo
from discovery import DiscoveryManager
from config import Config
from control_manager import ControlManager

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

    def do_GET(self):
        parts = self._get_url_path_parts()

        if self.path == "/ping":
            self._set_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        #if parts == ['api', 'v1', 'apps']: TODO refactor
        elif self.path == "/app":
            apps = self.discovery_manager.run_discovery()

            # Формируем метку времени в формате YYYYMMDD_HHMMSS с добавлением 4 часов
            last_update = (datetime.now() + timedelta(hours=7)).strftime("%Y%m%d_%H%M%S")

            response_data = {
                "server": {
                    "name": get_hostname(),
                    "ip": get_ip_address(),
                    "site-app": {
                        "applications": [app.to_dict() for app in apps],
                        "count": str(len(apps)),
                        "last_update": last_update
                    }
                }
            }
            self._set_headers()
            self.wfile.write(json.dumps(response_data, indent=4).encode("utf-8"))
            return
        
        if parts == ['api', 'v1', 'haproxy', 'backends'] and len(parts) == 5 and parts[3] == 'servers':
            backend_name = parts[2]
            try:
                servers_info = self.haproxy_controller.get_servers_info(backend_name)
                self._set_headers()
                self.wfile.write(json.dumps(servers_info, indent=4).encode("utf-8"))
            except Exception as e:
                self._send_error_response(500, str(e))
            return
                
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))


    def do_POST(self):
        parts = self._get_url_path_parts()
        
        # URL будет выглядеть так: /api/v1/control/{controller_name}/...
        if len(parts) >= 4 and parts[0:2] == ['api', 'v1', 'control']:
            controller_name = parts[2]
            controller = self.control_manager.get_controller(controller_name)
            
            if not controller:
                self._send_error_response(404, f"Controller '{controller_name}' not found.")
                return

            try:
                action_path = parts[3:]
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                body = json.loads(post_data.decode('utf-8'))
                
                result = controller.handle_action(action_path, body)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success", "result": result}).encode("utf-8"))
            except Exception as e:
                self._send_error_response(500, str(e))
            return    

    def log_message(self, format, *args):
        """Отключаем стандартный логгинг HTTP-сервера, чтобы управлять им централизованно."""
        pass

def run_server(discovery_manager: DiscoveryManager):
    """Создает HTTP-сервер и возвращает его экземпляр."""
    server_address = (Config.SERVER_HOST, Config.SERVER_PORT)
    # Внедряем менеджер в обработчик
    AgentRequestHandler.discovery_manager = discovery_manager
    
    httpd = HTTPServer(server_address, AgentRequestHandler)
    print(f"Starting server on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    return httpd