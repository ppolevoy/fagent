#!/usr/bin/env python3
"""
Docker Discoverer - Plugin для обнаружения Docker контейнеров
Версия: 1.0
"""

import logging
import socket
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
            state: Строка состояния, например "Up 2 hours" или "Exited (0) 3 hours ago"

        Returns:
            Базовый статус (running, exited, etc.)
        """
        if not state:
            return "unknown"

        state_lower = state.lower()

        if state_lower.startswith("up"):
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

                    # Получаем PID
                    pid = self.client.get_container_pid(container_id)

                    # Получаем docker-compose директорию
                    compose_dir = self.client.get_container_compose_dir(container_id)

                    # Получаем время запуска
                    start_time = self.client.get_container_start_time(container_id)
                    if start_time:
                        start_time = self._format_start_time(start_time)
                    else:
                        start_time = "Unknown"

                    # Определяем статус
                    base_status = self._extract_status_from_state(status_string)
                    app_status = self._map_docker_status(base_status)

                    # Создаем ApplicationInfo
                    app_info = ApplicationInfo(
                        name=container_name,
                        version=tag,
                        status=app_status,
                        start_time=start_time,
                        metadata={
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