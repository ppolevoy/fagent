# controllers/haproxy_controller.py
import logging
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

# Добавляем родительскую директорию в sys.path для корректных импортов
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from control import AbstractController
from plugins.haproxy_client import HAProxyClient, HAProxyConnectionError, HAProxyCommandError
from config import Config

logger = logging.getLogger(__name__)


class HAProxyController(AbstractController):
    """
    Контроллер для управления HAProxy через API.

    Поддерживает:
    - Получение списка бэкендов
    - Получение серверов в бэкенде
    - Управление состоянием серверов (ready, drain, maint)
    - Множественные инстансы HAProxy
    """

    def __init__(self):
        """Инициализация контроллера."""
        self.clients: Dict[str, HAProxyClient] = {}
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """
        Инициализация клиентов HAProxy.

        Поддерживает:
        - Единичный инстанс: HAPROXY_SOCKET_PATH
        - Множественные инстансы: HAPROXY_INSTANCES (JSON или comma-separated)
        """
        logger.info("Инициализация HAProxy клиентов")

        try:
            # Проверяем наличие множественных инстансов
            instances_config = getattr(Config, 'HAPROXY_INSTANCES', None)

            if instances_config:
                # Поддержка множественных инстансов
                # Формат: "name1:/path/to/socket1,name2:/path/to/socket2"
                if isinstance(instances_config, str):
                    for instance_def in instances_config.split(','):
                        instance_def = instance_def.strip()
                        if ':' in instance_def:
                            name, socket_path = instance_def.split(':', 1)
                            self._add_client(name.strip(), socket_path.strip())
                elif isinstance(instances_config, dict):
                    # Формат словаря: {"name1": "/path/to/socket1"}
                    for name, socket_path in instances_config.items():
                        self._add_client(name, socket_path)
            else:
                # Дефолтный единичный инстанс
                socket_path = Config.HAPROXY_SOCKET_PATH
                self._add_client('default', socket_path)

            if not self.clients:
                logger.warning("Не настроено ни одного HAProxy инстанса")
            else:
                logger.info(f"Инициализировано HAProxy инстансов: {len(self.clients)}")
                for name in self.clients.keys():
                    logger.info(f"  - {name}")

        except Exception as e:
            logger.error(f"Ошибка инициализации HAProxy клиентов: {e}", exc_info=True)

    def _add_client(self, name: str, socket_path: str) -> None:
        """
        Добавляет клиента HAProxy.

        Args:
            name: Имя инстанса
            socket_path: Путь к socket
        """
        try:
            timeout = getattr(Config, 'HAPROXY_TIMEOUT', 5.0)
            client = HAProxyClient(socket_path, timeout=timeout)

            # Проверяем доступность
            if client.health_check():
                self.clients[name] = client
                logger.info(f"HAProxy клиент '{name}' успешно инициализирован: {socket_path}")
            else:
                logger.error(f"HAProxy клиент '{name}' не прошел health check: {socket_path}")

        except HAProxyConnectionError as e:
            logger.error(f"Не удалось подключиться к HAProxy '{name}': {e}")
        except Exception as e:
            logger.error(f"Ошибка при добавлении HAProxy клиента '{name}': {e}", exc_info=True)

    def _get_client(self, instance_name: Optional[str] = None) -> HAProxyClient:
        """
        Получает клиента HAProxy по имени.

        Args:
            instance_name: Имя инстанса (или None для дефолтного)

        Returns:
            HAProxyClient: Клиент HAProxy

        Raises:
            ValueError: Если инстанс не найден
        """
        # Если не указан - берем первый доступный или 'default'
        if not instance_name:
            if 'default' in self.clients:
                return self.clients['default']
            elif self.clients:
                # Берем первый доступный
                instance_name = list(self.clients.keys())[0]
                return self.clients[instance_name]
            else:
                raise ValueError("Нет доступных HAProxy инстансов")

        # Ищем по имени
        if instance_name not in self.clients:
            available = ', '.join(self.clients.keys())
            raise ValueError(
                f"HAProxy инстанс '{instance_name}' не найден. "
                f"Доступные инстансы: {available}"
            )

        return self.clients[instance_name]

    def get_name(self) -> str:
        """Возвращает имя контроллера."""
        return "haproxy"

    def handle_get(self, path_parts: List[str], query_params: Dict[str, str]) -> Dict[str, Any]:
        """
        Обрабатывает GET запросы.

        Поддерживаемые пути:
        - /api/v1/haproxy/backends - список бэкендов
        - /api/v1/haproxy/backends/{backend}/servers - серверы в бэкенде
        - /api/v1/haproxy/{instance}/backends - список бэкендов инстанса
        - /api/v1/haproxy/{instance}/backends/{backend}/servers - серверы инстанса

        Args:
            path_parts: Части пути после /api/v1/haproxy/
            query_params: Параметры запроса

        Returns:
            Dict[str, Any]: Результат в стандартном формате
        """
        logger.info(f"GET запрос: path_parts={path_parts}, query_params={query_params}")

        try:
            if not path_parts:
                return self._error_response("Путь не указан", 400)

            # Проверяем первую часть пути
            first_part = path_parts[0]

            # Вариант 1: /backends/...
            if first_part == 'backends':
                instance_name = None
                path_offset = 0
            # Вариант 2: /{instance}/backends/...
            else:
                instance_name = first_part
                path_offset = 1

            # Получаем клиента
            client = self._get_client(instance_name)

            # Парсим остальной путь
            remaining_path = path_parts[path_offset:]

            if not remaining_path:
                return self._error_response("Неполный путь запроса", 400)

            # /backends - список бэкендов
            if remaining_path == ['backends']:
                backends = client.get_backends()
                return self._success_response({
                    'instance': instance_name or 'default',
                    'backends': backends,
                    'count': len(backends)
                })

            # /backends/{backend}/servers - серверы в бэкенде
            if len(remaining_path) == 3 and remaining_path[0] == 'backends' and remaining_path[2] == 'servers':
                backend_name = remaining_path[1]
                servers = client.get_backend_servers(backend_name)
                return self._success_response({
                    'instance': instance_name or 'default',
                    'backend': backend_name,
                    'servers': servers,
                    'count': len(servers)
                })

            return self._error_response(f"Неизвестный путь: {'/'.join(path_parts)}", 404)

        except ValueError as e:
            logger.warning(f"Ошибка валидации: {e}")
            return self._error_response(str(e), 400)

        except HAProxyConnectionError as e:
            logger.error(f"Ошибка подключения к HAProxy: {e}")
            return self._error_response(f"Ошибка подключения к HAProxy: {e}", 503)

        except Exception as e:
            logger.error(f"Неожиданная ошибка в handle_get: {e}", exc_info=True)
            return self._error_response(f"Внутренняя ошибка: {e}", 500)

    def handle_action(self, action_path: List[str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает POST запросы (действия).

        Поддерживаемые пути:
        - /api/v1/haproxy/backends/{backend}/servers/{server}/action
        - /api/v1/haproxy/{instance}/backends/{backend}/servers/{server}/action

        Body:
        {
            "action": "ready|drain|maint"
        }

        Args:
            action_path: Части пути после /api/v1/haproxy/
            body: Тело запроса

        Returns:
            Dict[str, Any]: Результат в стандартном формате
        """
        logger.info(f"POST запрос: action_path={action_path}, body={body}")

        try:
            # Валидация body
            if not body or 'action' not in body:
                return self._error_response("Поле 'action' обязательно в теле запроса", 400)

            action = body['action']

            # Проверяем валидность action
            if action not in HAProxyClient.VALID_STATES:
                return self._error_response(
                    f"Невалидный action '{action}'. Допустимые: {', '.join(HAProxyClient.VALID_STATES)}",
                    400
                )

            # Парсим путь
            # Формат 1: ['backends', 'mybackend', 'servers', 'server1', 'action']
            # Формат 2: ['instance1', 'backends', 'mybackend', 'servers', 'server1', 'action']

            if len(action_path) < 5:
                return self._error_response("Неполный путь запроса", 400)

            # Определяем, указан ли инстанс
            if action_path[0] == 'backends':
                instance_name = None
                path_offset = 0
            else:
                instance_name = action_path[0]
                path_offset = 1

            # Проверяем структуру пути
            remaining_path = action_path[path_offset:]

            if len(remaining_path) != 5:
                return self._error_response("Неверная структура пути", 400)

            if remaining_path[0] != 'backends' or remaining_path[2] != 'servers' or remaining_path[4] != 'action':
                return self._error_response(
                    "Ожидается путь: /backends/{backend}/servers/{server}/action",
                    400
                )

            backend_name = remaining_path[1]
            server_name = remaining_path[3]

            # Получаем клиента
            client = self._get_client(instance_name)

            # Выполняем действие
            logger.info(f"Установка состояния: {backend_name}/{server_name} -> {action}")
            success = client.set_server_state(backend_name, server_name, action)

            if success:
                return self._success_response({
                    'instance': instance_name or 'default',
                    'backend': backend_name,
                    'server': server_name,
                    'action': action,
                    'status': 'completed'
                }, message=f"Состояние сервера успешно изменено на '{action}'")
            else:
                return self._error_response("Не удалось изменить состояние сервера", 500)

        except ValueError as e:
            logger.warning(f"Ошибка валидации: {e}")
            return self._error_response(str(e), 400)

        except HAProxyCommandError as e:
            logger.error(f"Ошибка выполнения команды HAProxy: {e}")
            return self._error_response(f"Ошибка HAProxy: {e}", 502)

        except HAProxyConnectionError as e:
            logger.error(f"Ошибка подключения к HAProxy: {e}")
            return self._error_response(f"Ошибка подключения к HAProxy: {e}", 503)

        except Exception as e:
            logger.error(f"Неожиданная ошибка в handle_action: {e}", exc_info=True)
            return self._error_response(f"Внутренняя ошибка: {e}", 500)

    def _success_response(
        self,
        data: Any,
        message: Optional[str] = None,
        status_code: int = 200
    ) -> Dict[str, Any]:
        """
        Формирует успешный ответ в едином формате.

        Args:
            data: Данные ответа
            message: Опциональное сообщение
            status_code: HTTP код

        Returns:
            Dict[str, Any]: Форматированный ответ
        """
        response = {
            'success': True,
            'status_code': status_code,
            'data': data
        }

        if message:
            response['message'] = message

        return response

    def _error_response(
        self,
        error: str,
        status_code: int = 500
    ) -> Dict[str, Any]:
        """
        Формирует ответ об ошибке в едином формате.

        Args:
            error: Сообщение об ошибке
            status_code: HTTP код ошибки

        Returns:
            Dict[str, Any]: Форматированный ответ
        """
        return {
            'success': False,
            'status_code': status_code,
            'error': error
        }

    def get_instances(self) -> List[str]:
        """
        Возвращает список доступных HAProxy инстансов.

        Returns:
            List[str]: Список имен инстансов
        """
        return list(self.clients.keys())
