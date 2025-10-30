# plugins/haproxy_client.py
import socket
import logging
from typing import List, Dict, Optional, Any, Tuple, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class HAProxyConnectionError(Exception):
    """Ошибка подключения к HAProxy."""
    pass


class HAProxyCommandError(Exception):
    """Ошибка выполнения команды HAProxy."""
    pass


class HAProxyClient:
    """
    Клиент для взаимодействия с HAProxy через Unix Socket или TCP Socket.

    Поддерживает HAProxy версии 2.x и выше.

    Форматы socket_path:
    - Unix socket: /var/run/haproxy.sock
    - TCP IPv4: ipv4@192.168.1.15:7777
    """

    # Допустимые состояния сервера
    VALID_STATES = ['ready', 'drain', 'maint']

    # Таймаут по умолчанию (секунды)
    DEFAULT_TIMEOUT = 5.0

    def __init__(self, socket_path: str, timeout: float = DEFAULT_TIMEOUT):
        """
        Инициализация клиента HAProxy.

        Args:
            socket_path: Путь к Unix Socket или TCP адрес
                        Форматы:
                        - Unix: /var/run/haproxy.sock
                        - IPv4: ipv4@192.168.1.15:7777
            timeout: Таймаут для операций с сокетом (секунды)
        """
        self.socket_path_str = socket_path
        self.timeout = timeout

        # Определяем тип socket и парсим адрес
        self.socket_type, self.address = self._parse_socket_path(socket_path)

        logger.info(f"HAProxyClient инициализирован: type={self.socket_type}, "
                   f"address={self.address}, timeout={timeout}s")

        # Валидация в зависимости от типа
        self._validate_socket()

    def _parse_socket_path(self, socket_path: str) -> Tuple[str, Union[Path, Tuple[str, int]]]:
        """
        Парсит socket_path и определяет тип подключения.

        Args:
            socket_path: Строка с путем или адресом

        Returns:
            Tuple[str, Union[Path, Tuple[str, int]]]: (тип, адрес)
                - ('unix', Path) для Unix socket
                - ('tcp4', (host, port)) для IPv4

        Raises:
            HAProxyConnectionError: Если формат невалидный
        """
        socket_path = socket_path.strip()
        logger.info(f"Парсинг socket_path: {socket_path}")
        # TCP IPv4: ipv4@192.168.1.15:7777
        if socket_path.startswith('ipv4@'):
            address_str = socket_path[5:]  # Убираем 'ipv4@'
            
            # Парсим host:port
            if ':' not in address_str:
                raise HAProxyConnectionError(
                    f"Invalid IPv4 format: {socket_path}. Expected: ipv4@host:port"
                )

            host, port_str = address_str.rsplit(':', 1)
            try:
                port = int(port_str)
                if not (1 <= port <= 65535):
                    raise ValueError("Port out of range")
            except ValueError as e:
                raise HAProxyConnectionError(
                    f"Invalid port in IPv4 address: {port_str} ({e})"
                )

            logger.debug(f"Parsed as IPv4 TCP: {host}:{port}")
            return ('tcp4', (host, port))

        # Unix socket: /var/run/haproxy.sock
        else:
            socket_file = Path(socket_path)
            logger.debug(f"Parsed as Unix socket: {socket_file}")
            return ('unix', socket_file)

    def _validate_socket(self) -> None:
        """Проверка доступности socket в зависимости от типа."""
        if self.socket_type == 'unix':
            # Валидация Unix socket
            socket_file = self.address

            if not socket_file.exists():
                logger.error(f"HAProxy socket не существует: {socket_file}")
                raise HAProxyConnectionError(f"Socket file not found: {socket_file}")

            if not socket_file.is_socket():
                logger.error(f"Путь не является socket: {socket_file}")
                raise HAProxyConnectionError(f"Path is not a socket: {socket_file}")

            logger.debug(f"Unix socket валидирован: {socket_file}")

        elif self.socket_type == 'tcp4':
            # Для TCP просто проверяем формат адреса
            host, port = self.address
            logger.debug(f"TCP socket валидирован: {host}:{port}")
            # Реальная проверка подключения произойдет при первом _send_command

        else:
            raise HAProxyConnectionError(f"Unknown socket type: {self.socket_type}")

    def _send_command(self, command: str) -> str:
        """
        Отправляет команду в HAProxy через Unix Socket или TCP Socket.

        Args:
            command: Команда для выполнения

        Returns:
            str: Ответ от HAProxy

        Raises:
            HAProxyConnectionError: Ошибка подключения
            HAProxyCommandError: Ошибка выполнения команды
        """
        logger.debug(f"Отправка команды в HAProxy ({self.socket_type}): {command}")

        try:
            # Создаем сокет в зависимости от типа
            if self.socket_type == 'unix':
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                connect_address = str(self.address)
                logger.debug(f"Создан Unix socket, адрес: {connect_address}")

            elif self.socket_type == 'tcp4':
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                connect_address = self.address  # (host, port) tuple
                logger.debug(f"Создан IPv4 socket, адрес: {connect_address}")

            else:
                raise HAProxyConnectionError(f"Unsupported socket type: {self.socket_type}")

            sock.settimeout(self.timeout)

            try:
                # Подключаемся к HAProxy
                sock.connect(connect_address)
                logger.debug(f"Подключение установлено")

                # Отправляем команду (HAProxy ожидает \n в конце)
                sock.sendall(f"{command}\n".encode('utf-8'))
                logger.debug(f"Команда отправлена")

                # Получаем ответ
                response = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk

                result = response.decode('utf-8')
                logger.debug(f"Получен ответ от HAProxy ({len(result)} байт)")

                return result

            finally:
                sock.close()
                logger.debug("Socket закрыт")

        except socket.timeout:
            error_msg = f"Таймаут при выполнении команды: {command}"
            logger.error(error_msg)
            raise HAProxyConnectionError(error_msg)

        except socket.error as e:
            error_msg = f"Ошибка socket при выполнении команды '{command}': {e}"
            logger.error(error_msg)
            raise HAProxyConnectionError(error_msg)

        except Exception as e:
            error_msg = f"Неожиданная ошибка при выполнении команды '{command}': {e}"
            logger.error(error_msg, exc_info=True)
            raise HAProxyCommandError(error_msg)

    def _parse_csv_response(self, response: str) -> List[Dict[str, str]]:
        """
        Парсит CSV ответ от HAProxy.

        Args:
            response: CSV ответ от HAProxy

        Returns:
            List[Dict[str, str]]: Список словарей с данными
        """
        lines = response.strip().split('\n')
        if not lines:
            return []

        # Первая строка - заголовки (начинается с '# ')
        header_line = lines[0]
        if not header_line.startswith('#'):
            logger.warning("CSV ответ не содержит заголовков")
            return []

        # Убираем '# ' и разбиваем по запятым
        headers = [h.strip() for h in header_line[2:].split(',')]

        result = []
        for line in lines[1:]:
            if not line or line.startswith('#'):
                continue

            values = [v.strip() for v in line.split(',')]

            # Проверяем соответствие количества значений и заголовков
            if len(values) != len(headers):
                logger.warning(f"Пропуск строки с несоответствующим количеством полей: {line[:50]}...")
                continue

            result.append(dict(zip(headers, values)))

        return result

    def get_info(self) -> Dict[str, str]:
        """
        Получает общую информацию о HAProxy.

        Returns:
            Dict[str, str]: Информация о HAProxy
        """
        logger.info("Получение информации о HAProxy")

        try:
            response = self._send_command("show info")

            info = {}
            for line in response.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()

            logger.debug(f"Получена информация о HAProxy: версия={info.get('Version', 'unknown')}")
            return info

        except Exception as e:
            logger.error(f"Ошибка получения информации о HAProxy: {e}")
            raise

    def get_backends(self) -> List[str]:
        """
        Получает список всех бэкендов.

        Returns:
            List[str]: Список имен бэкендов
        """
        logger.info("Получение списка бэкендов")

        try:
            response = self._send_command("show stat")
            stats = self._parse_csv_response(response)

            # Извлекаем уникальные имена бэкендов
            # В HAProxy stat: pxname - имя proxy (frontend/backend)
            # svname - имя сервера или BACKEND/FRONTEND
            backends = set()
            for entry in stats:
                pxname = entry.get('pxname', '')
                svname = entry.get('svname', '')
                # Ищем записи типа BACKEND (это маркер бэкенда)
                if svname == 'BACKEND':
                    backends.add(pxname)

            result = sorted(list(backends))
            logger.info(f"Найдено бэкендов: {len(result)}")
            logger.debug(f"Бэкенды: {result}")

            return result

        except Exception as e:
            logger.error(f"Ошибка получения списка бэкендов: {e}")
            raise

    def get_backend_servers(self, backend_name: str) -> List[Dict[str, str]]:
        """
        Получает информацию о всех серверах в указанном бэкенде.

        Args:
            backend_name: Имя бэкенда

        Returns:
            List[Dict[str, str]]: Список серверов с их параметрами
        """
        logger.info(f"Получение серверов для бэкенда: {backend_name}")

        try:
            response = self._send_command("show stat")
            stats = self._parse_csv_response(response)

            # Фильтруем серверы нужного бэкенда
            servers = []
            for entry in stats:
                if entry.get('pxname', '') == backend_name and entry.get('svname', '') not in ['BACKEND', 'FRONTEND']:
                    # Оставляем только полезные поля
                    server_info = {
                        'name': entry.get('svname', ''),
                        'status': entry.get('status', ''),
                        'weight': entry.get('weight', ''),
                        'check_status': entry.get('check_status', ''),
                        'check_duration': entry.get('check_duration', ''),
                        'last_chg': entry.get('last_chg', ''),
                        'downtime': entry.get('downtime', ''),
                        'addr': entry.get('addr', ''),
                        'cookie': entry.get('cookie', ''),
                    }
                    servers.append(server_info)

            logger.info(f"Найдено серверов в бэкенде '{backend_name}': {len(servers)}")
            return servers

        except Exception as e:
            logger.error(f"Ошибка получения серверов для бэкенда '{backend_name}': {e}")
            raise

    def set_server_state(self, backend_name: str, server_name: str, state: str) -> bool:
        """
        Устанавливает состояние сервера.

        Args:
            backend_name: Имя бэкенда
            server_name: Имя сервера
            state: Новое состояние ('ready', 'drain', 'maint')

        Returns:
            bool: True если успешно

        Raises:
            ValueError: Если state невалидный
            HAProxyCommandError: Если команда не выполнена
        """
        # Валидация состояния
        if state not in self.VALID_STATES:
            raise ValueError(
                f"Invalid state '{state}'. "
                f"Allowed values: {', '.join(self.VALID_STATES)}"
            )

        logger.info(f"Установка состояния сервера: {backend_name}/{server_name} -> {state}")

        try:
            command = f"set server {backend_name}/{server_name} state {state}"
            response = self._send_command(command)

            # HAProxy возвращает пустой ответ при успехе или сообщение об ошибке
            if response.strip():
                # Если есть ответ, проверяем на ошибки
                if 'error' in response.lower() or 'invalid' in response.lower():
                    logger.error(f"HAProxy вернул ошибку: {response}")
                    raise HAProxyCommandError(f"HAProxy error: {response}")

            logger.info(f"Состояние сервера {backend_name}/{server_name} успешно изменено на '{state}'")
            return True

        except HAProxyCommandError:
            raise
        except Exception as e:
            error_msg = f"Failed to set server state {backend_name}/{server_name}: {e}"
            logger.error(error_msg)
            raise HAProxyCommandError(error_msg)

    def get_server_state(self, backend_name: str, server_name: str) -> Optional[Dict[str, str]]:
        """
        Получает информацию о конкретном сервере.

        Args:
            backend_name: Имя бэкенда
            server_name: Имя сервера

        Returns:
            Optional[Dict[str, str]]: Информация о сервере или None если не найден
        """
        logger.info(f"Получение состояния сервера: {backend_name}/{server_name}")

        try:
            servers = self.get_backend_servers(backend_name)

            for server in servers:
                if server.get('name', '') == server_name:
                    logger.debug(f"Сервер найден: {server}")
                    return server

            logger.warning(f"Сервер {backend_name}/{server_name} не найден")
            return None

        except Exception as e:
            logger.error(f"Ошибка получения состояния сервера {backend_name}/{server_name}: {e}")
            raise

    def health_check(self) -> bool:
        """
        Проверяет доступность HAProxy.

        Returns:
            bool: True если HAProxy доступен
        """
        try:
            info = self.get_info()
            return 'Version' in info
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
