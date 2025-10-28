# server.py
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List

from models import ApplicationInfo
from discovery import DiscoveryManager
from config import Config

class AgentRequestHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов."""
    
    # Внедряем зависимость через атрибут класса (простой способ для примера)
    discovery_manager: DiscoveryManager = None

    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._set_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        elif self.path == "/api/v1/apps":
            apps = self.discovery_manager.run_discovery()
            response_data = {
                "server": {
                    "name": "hostname_placeholder", # TODO: get real hostname
                    "applications": [app.to_dict() for app in apps]
                }
            }
            self._set_headers()
            self.wfile.write(json.dumps(response_data, indent=4).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def log_message(self, format, *args):
        """Отключаем стандартный логгинг HTTP-сервера, чтобы управлять им централизованно."""
        pass

def run_server(discovery_manager: DiscoveryManager):
    """Запускает HTTP-сервер."""
    server_address = (Config.SERVER_HOST, Config.SERVER_PORT)
    # Внедряем менеджер в обработчик
    AgentRequestHandler.discovery_manager = discovery_manager
    httpd = HTTPServer(server_address, AgentRequestHandler)
    print(f"Starting server on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    httpd.serve_forever()