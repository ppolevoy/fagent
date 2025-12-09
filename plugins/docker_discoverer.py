#!/usr/bin/env python3
"""
Docker Discoverer - Plugin для обнаружения Docker контейнеров
Версия: 2.0 (универсальная)

Этот плагин работает с ОБЕИМИ версиями docker_client:
- docker-py версия (быстрая) - использует _container_obj для оптимизации
- subprocess версия (совместимая) - использует методы клиента

Автоматически определяет какая версия docker_client используется.
"""

import logging
import socket
import os
from typing import List
from datetime import datetime

from discovery import AbstractDiscoverer
from models import ApplicationInfo
from plugins.docker_client import DockerClient
import config

logger = logging.getLogger(__name__)


class DockerDiscoverer(AbstractDiscoverer):
    """Plugin для обнаружения Docker контейнеров"""

    def __init__(self):
        """Инициализация Docker discoverer"""
        super().__init__()
        self.enabled = getattr(config, 'DOCKER_DISCOVERY_ENABLED', True)
        self.timeout = getattr(config, 'DOCKER_REQUEST_TIMEOUT', 10)

        if self.enabled:
            try:
                self.client = DockerClient(timeout=self.timeout)
                logger.info("Docker discoverer инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации Docker client: {e}")
                self.enabled = False
                self.client = None
        else:
            logger.info("Docker discoverer отключен в конфигурации")
            self.client = None

        # Инициализация Eureka client для обогащения данных (опционально)
        self.eureka_client = None
        self.eureka_enabled = getattr(config, 'EUREKA_DISCOVERY_ENABLED', False)

        if self.eureka_enabled:
            try:
                from plugins.eureka_client import EurekaClient
                eureka_host = getattr(config, 'EUREKA_HOST', 'fdse.f.ftc.ru')
                eureka_port = getattr(config, 'EUREKA_PORT', 8761)
                eureka_timeout = getattr(config, 'EUREKA_REQUEST_TIMEOUT', 10)

                self.eureka_client = EurekaClient(
                    host=eureka_host,
                    port=eureka_port,
                    timeout=eureka_timeout
                )
                logger.info("Docker discoverer: Eureka integration enabled")
            except Exception as e:
                logger.warning(f"Docker discoverer: Не удалось инициализировать Eureka client: {e}")
                self.eureka_client = None

    def _get_server_ip(self) -> str:
        """Получение IP адреса сервера"""
        try:
            # Пытаемся получить IP через подключение к внешнему хосту
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            # Fallback на localhost
            return "127.0.0.1"

    def _map_docker_status(self, docker_status: str) -> str:
        """
        Преобразование статуса Docker в статус ApplicationInfo

        Args:
            docker_status: Статус из Docker (running, exited, paused, etc.)

        Returns:
            Статус для ApplicationInfo
        """
        status_mapping = {
            "running": "online",
            "exited": "offline",
            "paused": "maintenance",
            "restarting": "restarting",
            "created": "offline",
            "removing": "offline",
            "dead": "offline"
        }

        # Docker статус может быть сложным, например "Up 2 hours"
        docker_status_lower = docker_status.lower()

        for docker_state, app_state in status_mapping.items():
            if docker_state in docker_status_lower:
                return app_state

        # Если статус начинается с "Up", считаем online
        if docker_status_lower.startswith("up"):
            return "online"

        # По умолчанию - unknown
        return "unknown"

    def _extract_status_from_state(self, state: str) -> str:
        """
        Извлечение базового статуса из строки состояния Docker

        Args:
            state: Строка состояния, например "Up 2 hours", "Exited (0) 3 hours ago", или базовый статус "running", "exited"

        Returns:
            Базовый статус (running, exited, etc.)
        """
        if not state:
            return "unknown"

        state_lower = state.lower()

        # Сначала проверяем базовые статусы (которые приходят от container.status)
        if state_lower == "running":
            return "running"
        elif state_lower == "exited":
            return "exited"
        elif state_lower == "paused":
            return "paused"
        elif state_lower == "restarting":
            return "restarting"
        elif state_lower == "created":
            return "created"
        elif state_lower == "removing":
            return "removing"
        elif state_lower == "dead":
            return "dead"
        # Потом проверяем человекочитаемые строки (для обратной совместимости с docker ps)
        elif state_lower.startswith("up"):
            return "running"
        elif "exited" in state_lower:
            return "exited"
        elif "paused" in state_lower:
            return "paused"
        elif "restarting" in state_lower:
            return "restarting"
        elif "created" in state_lower:
            return "created"
        else:
            return "unknown"

    def _format_start_time(self, start_time: str) -> str:
        """
        Форматирование времени запуска контейнера

        Args:
            start_time: Время в ISO формате от Docker

        Returns:
            Отформатированное время
        """
        if not start_time:
            return "Unknown"

        try:
            # Docker возвращает время в формате: 2025-11-12T20:42:09.346234221Z
            # Убираем наносекунды для простоты
            if '.' in start_time:
                # Оставляем только микросекунды (6 цифр)
                base_time, fraction = start_time.split('.')
                if 'Z' in fraction:
                    fraction = fraction.replace('Z', '')
                    # Берем первые 6 цифр для микросекунд
                    fraction = fraction[:6].ljust(6, '0')
                    start_time = f"{base_time}.{fraction}Z"

            return start_time
        except Exception as e:
            logger.debug(f"Ошибка форматирования времени {start_time}: {e}")
            return start_time

    def _extract_container_details(self, container: dict) -> dict:
        """
        Извлечение деталей контейнера из _container_obj (без дополнительных API вызовов).

        Args:
            container: Словарь с данными контейнера от get_containers()

        Returns:
            dict с pid, start_time, compose_dir
        """
        container_obj = container.get('_container_obj')

        if not container_obj:
            # Fallback на старый метод если объект недоступен
            container_id = container.get('ID', '')
            return {
                'pid': self.client.get_container_pid(container_id) if container_id else None,
                'start_time': self.client.get_container_start_time(container_id) if container_id else None,
                'compose_dir': self.client.get_container_compose_dir(container_id) if container_id else None
            }

        # Быстрый путь: извлекаем из уже загруженного объекта
        try:
            state = container_obj.attrs.get('State', {})
            pid = state.get('Pid')
            if pid == 0:
                pid = None

            start_time = state.get('StartedAt')
            if start_time == "0001-01-01T00:00:00Z":
                start_time = None

            # Compose директория из labels
            labels = container_obj.labels or {}
            compose_path = labels.get('com.docker.compose.project.config_files')
            compose_dir = None
            if compose_path:
                compose_dir = os.path.dirname(compose_path) if os.path.isfile(compose_path) else compose_path

            return {
                'pid': pid,
                'start_time': start_time,
                'compose_dir': compose_dir
            }

        except Exception as e:
            logger.warning(f"Ошибка извлечения деталей контейнера: {e}")
            return {'pid': None, 'start_time': None, 'compose_dir': None}

    def _load_eureka_apps_map(self) -> dict:
        """
        Предзагрузка всех приложений из Eureka в словарь для быстрого поиска.

        Returns:
            dict: Словарь {ip:port -> eureka_app_data}
        """
        eureka_map = {}

        if not self.eureka_client:
            return eureka_map

        try:
            apps = self.eureka_client.get_applications()

            for app in apps:
                ip = app.get('ip', '')
                port = app.get('port', 0)

                if ip and port:
                    key = f"{ip}:{port}"
                    eureka_map[key] = {
                        "eureka_registered": True,
                        "eureka_instance_id": app.get("instance_id", ""),
                        "eureka_app_name": app.get("app_name", ""),
                        "eureka_status": app.get("status", "UNKNOWN"),
                        "eureka_url": app.get("home_page_url", ""),
                        "eureka_health_url": app.get("health_check_url", ""),
                        "eureka_vip": app.get("vip_address", "")
                    }

            logger.debug(f"Загружено {len(eureka_map)} приложений из Eureka")

        except Exception as e:
            logger.warning(f"Ошибка загрузки приложений из Eureka: {e}")

        return eureka_map

    def discover(self) -> List[ApplicationInfo]:
        """
        Обнаружение Docker контейнеров

        Returns:
            Список ApplicationInfo для найденных контейнеров
        """
        if not self.enabled or not self.client:
            logger.debug("Docker discoverer отключен или не инициализирован")
            return []

        applications = []

        try:
            # Получаем список контейнеров (только запущенные)
            containers = self.client.get_containers(all_containers=False)

            if not containers:
                logger.info("Docker контейнеры не найдены")
                return []

            server_ip = self._get_server_ip()

            # Предзагружаем Eureka данные ОДИН раз (вместо запроса на каждый контейнер)
            eureka_apps_map = {}
            if self.eureka_client:
                eureka_apps_map = self._load_eureka_apps_map()
                logger.debug(f"Eureka: предзагружено {len(eureka_apps_map)} приложений")

            for container in containers:
                try:
                    # Извлекаем базовую информацию
                    container_id = container.get('ID', '')
                    container_name = container.get('Names', '').lstrip('/')
                    image_full = container.get('Image', '')
                    status_string = container.get('Status', '')
                    ports_string = container.get('Ports', '')

                    if not container_id or not container_name:
                        logger.warning(f"Пропущен контейнер без ID или имени: {container}")
                        continue

                    # Парсим образ и тег
                    image, tag = self.client.parse_image_tag(image_full)

                    # Извлекаем порт
                    port = self.client.parse_port_mapping(ports_string)

                    # Извлекаем всё из уже загруженного объекта (0 дополнительных API вызовов)
                    details = self._extract_container_details(container)
                    pid = details['pid']
                    compose_dir = details['compose_dir']
                    start_time = details['start_time']
                    if start_time:
                        start_time = self._format_start_time(start_time)
                    else:
                        start_time = "Unknown"

                    # Определяем статус
                    base_status = self._extract_status_from_state(status_string)
                    app_status = self._map_docker_status(base_status)

                    # Базовые метаданные
                    metadata = {
                        "source": "docker",
                        "container_id": container_id,
                        "container_name": container_name,
                        "image": image,
                        "tag": tag,
                        "image_full": image_full,
                        "ip": server_ip,
                        "port": port if port else None,
                        "pid": pid if pid else None,
                        "compose_project_dir": compose_dir,
                        "docker_status": status_string,
                        "docker_state": base_status
                    }

                    # Обогащение данными из Eureka: O(1) lookup вместо HTTP запроса
                    if eureka_apps_map and port:
                        eureka_key = f"{server_ip}:{port}"
                        eureka_data = eureka_apps_map.get(eureka_key)
                        if eureka_data:
                            metadata.update(eureka_data)
                            logger.debug(f"Docker контейнер {container_name} найден в Eureka: {eureka_data.get('eureka_instance_id')}")
                        else:
                            metadata["eureka_registered"] = False

                    # Создаем ApplicationInfo
                    app_info = ApplicationInfo(
                        name=container_name,
                        version=tag,
                        status=app_status,
                        start_time=start_time,
                        metadata=metadata
                    )

                    applications.append(app_info)
                    logger.debug(f"Обнаружен Docker контейнер: {container_name} ({container_id[:12]})")

                except Exception as e:
                    logger.error(f"Ошибка обработки контейнера {container}: {e}")
                    continue

            logger.info(f"Docker discoverer обнаружил {len(applications)} контейнеров")

        except Exception as e:
            logger.error(f"Критическая ошибка в Docker discoverer: {e}")

        return applications


if __name__ == "__main__":
    # Тестирование discoverer
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Включаем Docker discovery для теста
    config.DOCKER_DISCOVERY_ENABLED = True
    config.DOCKER_REQUEST_TIMEOUT = 10

    discoverer = DockerDiscoverer()
    apps = discoverer.discover()

    print(f"\n=== Найдено Docker приложений: {len(apps)} ===\n")

    for app in apps:
        print(f"Приложение: {app.name}")
        print(f"  Версия: {app.version}")
        print(f"  Статус: {app.status}")
        print(f"  Время запуска: {app.start_time}")
        print(f"  Метаданные:")
        for key, value in app.metadata.items():
            if value is not None:
                print(f"    {key}: {value}")
        print()