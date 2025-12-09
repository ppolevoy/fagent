#!/usr/bin/env python3
"""
Eureka Controller - API для управления приложениями в Eureka
"""
import logging
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

# Добавляем родительскую директорию в sys.path для корректных импортов
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from control import AbstractController
from plugins.eureka_client import EurekaClient
from config import Config

logger = logging.getLogger(__name__)


class EurekaController(AbstractController):
    """
    Контроллер для управления приложениями в Eureka.

    API Endpoints:
    - GET  /api/v1/eureka/apps                      - Список всех приложений
    - GET  /api/v1/eureka/apps/{instance_id}        - Информация о приложении
    - GET  /api/v1/eureka/apps/{instance_id}/health - Health check
    - POST /api/v1/eureka/apps/{instance_id}/pause    - Pause приложения
    - POST /api/v1/eureka/apps/{instance_id}/shutdown - Graceful shutdown
    - POST /api/v1/eureka/apps/{instance_id}/loglevel - Изменить log level
    """

    def __init__(self):
        """Инициализация контроллера."""
        self.client: Optional[EurekaClient] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Инициализация Eureka клиента."""
        try:
            if not Config.EUREKA_DISCOVERY_ENABLED:
                logger.warning("Eureka discovery отключен (EUREKA_DISCOVERY_ENABLED=false)")
                return

            self.client = EurekaClient(
                host=Config.EUREKA_HOST,
                port=Config.EUREKA_PORT,
                timeout=Config.EUREKA_REQUEST_TIMEOUT
            )
            logger.info(f"Eureka контроллер инициализирован: {Config.EUREKA_HOST}:{Config.EUREKA_PORT}")

        except Exception as e:
            logger.error(f"Ошибка инициализации Eureka контроллера: {e}", exc_info=True)

    def get_name(self) -> str:
        """Возвращает имя контроллера для API маршрутизации."""
        return "eureka"

    def handle_get(self, path_parts: List[str], query_params: Dict[str, str]) -> Dict[str, Any]:
        """
        Обработка GET запросов.

        Поддерживаемые маршруты:
        - /api/v1/eureka/apps - список всех приложений
        - /api/v1/eureka/apps/{instance_id} - информация о конкретном приложении
        - /api/v1/eureka/apps/{instance_id}/health - health check приложения
        """
        if not self.client:
            return {
                "success": False,
                "status_code": 503,
                "error": "Eureka client is not initialized. Check EUREKA_DISCOVERY_ENABLED setting."
            }

        # GET /api/v1/eureka/apps
        if not path_parts or (len(path_parts) == 1 and path_parts[0] == "apps"):
            return self._get_all_apps()

        # GET /api/v1/eureka/apps/{instance_id}
        if len(path_parts) == 2 and path_parts[0] == "apps":
            instance_id = path_parts[1]
            return self._get_app_by_instance_id(instance_id)

        # GET /api/v1/eureka/apps/{instance_id}/health
        if len(path_parts) == 3 and path_parts[0] == "apps" and path_parts[2] == "health":
            instance_id = path_parts[1]
            return self._get_app_health(instance_id)

        return {
            "success": False,
            "status_code": 404,
            "error": f"Unknown GET endpoint: /api/v1/eureka/{'/'.join(path_parts)}"
        }

    def handle_action(self, action_path: List[str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка POST запросов (команды управления).

        Поддерживаемые маршруты:
        - /api/v1/eureka/apps/{instance_id}/pause - pause приложения
        - /api/v1/eureka/apps/{instance_id}/shutdown - graceful shutdown
        - /api/v1/eureka/apps/{instance_id}/loglevel - изменить log level
        """
        if not self.client:
            return {
                "success": False,
                "status_code": 503,
                "error": "Eureka client is not initialized. Check EUREKA_DISCOVERY_ENABLED setting."
            }

        # POST /api/v1/eureka/apps/{instance_id}/pause
        if len(action_path) == 3 and action_path[0] == "apps" and action_path[2] == "pause":
            instance_id = action_path[1]
            return self._pause_app(instance_id)

        # POST /api/v1/eureka/apps/{instance_id}/shutdown
        if len(action_path) == 3 and action_path[0] == "apps" and action_path[2] == "shutdown":
            instance_id = action_path[1]
            return self._shutdown_app(instance_id)

        # POST /api/v1/eureka/apps/{instance_id}/loglevel
        if len(action_path) == 3 and action_path[0] == "apps" and action_path[2] == "loglevel":
            instance_id = action_path[1]
            logger_name = body.get("logger", "ROOT")
            level = body.get("level", "")

            if not level:
                return {
                    "success": False,
                    "status_code": 400,
                    "error": "Missing required parameter: 'level'"
                }

            return self._set_app_loglevel(instance_id, logger_name, level)

        return {
            "success": False,
            "status_code": 404,
            "error": f"Unknown POST endpoint: /api/v1/eureka/{'/'.join(action_path)}"
        }

    def _get_all_apps(self) -> Dict[str, Any]:
        """
        Получить список всех приложений из Eureka.

        Returns:
            Dict с полями:
            - success: bool
            - status_code: int
            - data: List[Dict] - список приложений
        """
        try:
            apps = self.client.get_applications()

            return {
                "success": True,
                "status_code": 200,
                "data": {
                    "total": len(apps),
                    "applications": apps
                }
            }

        except Exception as e:
            logger.error(f"Ошибка получения списка приложений: {e}", exc_info=True)
            return {
                "success": False,
                "status_code": 500,
                "error": f"Failed to get applications: {str(e)}"
            }

    def _get_app_by_instance_id(self, instance_id: str) -> Dict[str, Any]:
        """
        Получить информацию о конкретном приложении по instance_id.

        Args:
            instance_id: Идентификатор инстанса (например, "192.168.1.100:my-service:8080")

        Returns:
            Dict с информацией о приложении или ошибкой
        """
        try:
            apps = self.client.get_applications()

            # Ищем приложение с указанным instance_id
            for app in apps:
                if app.get("instance_id") == instance_id:
                    return {
                        "success": True,
                        "status_code": 200,
                        "data": app
                    }

            return {
                "success": False,
                "status_code": 404,
                "error": f"Application with instance_id '{instance_id}' not found in Eureka"
            }

        except Exception as e:
            logger.error(f"Ошибка получения приложения {instance_id}: {e}", exc_info=True)
            return {
                "success": False,
                "status_code": 500,
                "error": f"Failed to get application: {str(e)}"
            }

    def _get_app_health(self, instance_id: str) -> Dict[str, Any]:
        """
        Проверить здоровье приложения через /actuator/health.

        Args:
            instance_id: Идентификатор инстанса

        Returns:
            Dict с результатом health check
        """
        try:
            # Сначала найдем приложение
            apps = self.client.get_applications()
            app = None

            for a in apps:
                if a.get("instance_id") == instance_id:
                    app = a
                    break

            if not app:
                return {
                    "success": False,
                    "status_code": 404,
                    "error": f"Application with instance_id '{instance_id}' not found in Eureka"
                }

            # Проверяем здоровье
            home_page_url = app.get("home_page_url", "")
            if not home_page_url:
                return {
                    "success": False,
                    "status_code": 400,
                    "error": f"Application '{instance_id}' does not have home_page_url"
                }

            health_result = self.client.check_app_health(home_page_url)

            return {
                "success": True,
                "status_code": 200,
                "data": {
                    "instance_id": instance_id,
                    "app_name": app.get("app_name"),
                    "health": health_result
                }
            }

        except Exception as e:
            logger.error(f"Ошибка health check для {instance_id}: {e}", exc_info=True)
            return {
                "success": False,
                "status_code": 500,
                "error": f"Failed to check health: {str(e)}"
            }

    def _pause_app(self, instance_id: str) -> Dict[str, Any]:
        """
        Отправить команду pause приложению.

        Args:
            instance_id: Идентификатор инстанса

        Returns:
            Dict с результатом операции
        """
        try:
            # Найдем приложение
            apps = self.client.get_applications()
            app = None

            for a in apps:
                if a.get("instance_id") == instance_id:
                    app = a
                    break

            if not app:
                return {
                    "success": False,
                    "status_code": 404,
                    "error": f"Application with instance_id '{instance_id}' not found in Eureka"
                }

            # Отправляем pause
            home_page_url = app.get("home_page_url", "")
            if not home_page_url:
                return {
                    "success": False,
                    "status_code": 400,
                    "error": f"Application '{instance_id}' does not have home_page_url"
                }

            pause_result = self.client.pause_app(home_page_url)

            # Проверяем результат
            if pause_result.get("success"):
                return {
                    "success": True,
                    "status_code": 200,
                    "data": {
                        "instance_id": instance_id,
                        "app_name": app.get("app_name"),
                        "message": pause_result.get("message"),
                        "details": pause_result.get("details", {})
                    }
                }
            else:
                return {
                    "success": False,
                    "status_code": 500,
                    "data": {
                        "instance_id": instance_id,
                        "app_name": app.get("app_name"),
                        "error": pause_result.get("message")
                    }
                }

        except Exception as e:
            logger.error(f"Ошибка pause для {instance_id}: {e}", exc_info=True)
            return {
                "success": False,
                "status_code": 500,
                "error": f"Failed to pause application: {str(e)}"
            }

    def _shutdown_app(self, instance_id: str) -> Dict[str, Any]:
        """
        Отправить команду graceful shutdown приложению.

        Args:
            instance_id: Идентификатор инстанса

        Returns:
            Dict с результатом операции
        """
        try:
            # Найдем приложение
            apps = self.client.get_applications()
            app = None

            for a in apps:
                if a.get("instance_id") == instance_id:
                    app = a
                    break

            if not app:
                return {
                    "success": False,
                    "status_code": 404,
                    "error": f"Application with instance_id '{instance_id}' not found in Eureka"
                }

            # Отправляем shutdown
            home_page_url = app.get("home_page_url", "")
            if not home_page_url:
                return {
                    "success": False,
                    "status_code": 400,
                    "error": f"Application '{instance_id}' does not have home_page_url"
                }

            shutdown_result = self.client.shutdown_app(home_page_url)

            # Проверяем результат
            if shutdown_result.get("success"):
                return {
                    "success": True,
                    "status_code": 200,
                    "data": {
                        "instance_id": instance_id,
                        "app_name": app.get("app_name"),
                        "message": shutdown_result.get("message"),
                        "details": shutdown_result.get("details", {})
                    }
                }
            else:
                return {
                    "success": False,
                    "status_code": 500,
                    "data": {
                        "instance_id": instance_id,
                        "app_name": app.get("app_name"),
                        "error": shutdown_result.get("message")
                    }
                }

        except Exception as e:
            logger.error(f"Ошибка shutdown для {instance_id}: {e}", exc_info=True)
            return {
                "success": False,
                "status_code": 500,
                "error": f"Failed to shutdown application: {str(e)}"
            }

    def _set_app_loglevel(self, instance_id: str, logger_name: str, level: str) -> Dict[str, Any]:
        """
        Изменить уровень логирования приложения.

        Args:
            instance_id: Идентификатор инстанса
            logger_name: Имя логгера (например, "ROOT", "com.example.myapp")
            level: Уровень логирования (TRACE, DEBUG, INFO, WARN, ERROR, OFF)

        Returns:
            Dict с результатом операции
        """
        try:
            # Найдем приложение
            apps = self.client.get_applications()
            app = None

            for a in apps:
                if a.get("instance_id") == instance_id:
                    app = a
                    break

            if not app:
                return {
                    "success": False,
                    "status_code": 404,
                    "error": f"Application with instance_id '{instance_id}' not found in Eureka"
                }

            # Изменяем log level
            home_page_url = app.get("home_page_url", "")
            if not home_page_url:
                return {
                    "success": False,
                    "status_code": 400,
                    "error": f"Application '{instance_id}' does not have home_page_url"
                }

            loglevel_result = self.client.set_app_loglevel(home_page_url, logger_name, level)

            # Проверяем результат
            if loglevel_result.get("success"):
                return {
                    "success": True,
                    "status_code": 200,
                    "data": {
                        "instance_id": instance_id,
                        "app_name": app.get("app_name"),
                        "logger": logger_name,
                        "level": level.upper(),
                        "message": loglevel_result.get("message")
                    }
                }
            else:
                return {
                    "success": False,
                    "status_code": 400,
                    "data": {
                        "instance_id": instance_id,
                        "app_name": app.get("app_name"),
                        "logger": logger_name,
                        "error": loglevel_result.get("message")
                    }
                }

        except Exception as e:
            logger.error(f"Ошибка изменения log level для {instance_id}: {e}", exc_info=True)
            return {
                "success": False,
                "status_code": 500,
                "error": f"Failed to set log level: {str(e)}"
            }


if __name__ == "__main__":
    # Простое тестирование контроллера
    logging.basicConfig(level=logging.DEBUG)

    print("=== Тестирование Eureka Controller ===\n")

    controller = EurekaController()
    print(f"Имя контроллера: {controller.get_name()}")

    if controller.client:
        # Тест получения списка приложений
        print("\n1. Получение списка приложений:")
        result = controller.handle_get(["apps"], {})
        print(f"   Success: {result['success']}")
        if result['success']:
            print(f"   Total apps: {result['data']['total']}")

            if result['data']['total'] > 0:
                # Тест получения конкретного приложения
                first_app = result['data']['applications'][0]
                instance_id = first_app['instance_id']
                print(f"\n2. Получение приложения {instance_id}:")
                result2 = controller.handle_get(["apps", instance_id], {})
                print(f"   Success: {result2['success']}")

                # Тест health check
                print(f"\n3. Health check для {instance_id}:")
                result3 = controller.handle_get(["apps", instance_id, "health"], {})
                print(f"   Success: {result3['success']}")
                if result3['success']:
                    print(f"   Health status: {result3['data']['health']['status']}")
    else:
        print("Eureka клиент не инициализирован. Проверьте настройки.")
