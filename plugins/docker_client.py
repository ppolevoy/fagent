#!/usr/bin/env python3
"""
Docker Client (docker-py version) 
Версия: 2.0 (docker-py)

- Python 3.7+
- docker>=7.0.0 (установка: pip install docker>=7.0.0)

"""

import docker
import logging
import os
from typing import List, Dict, Optional, Tuple
from docker.errors import DockerException, APIError, NotFound

logger = logging.getLogger(__name__)


class DockerClient:
    """Клиент для работы с Docker через официальную библиотеку docker-py"""

    def __init__(self, timeout: int = 10):
        """
        Инициализация Docker клиента

        Args:
            timeout: Таймаут для выполнения команд в секундах
        """
        self.timeout = timeout
        self.client = None
        self._check_docker_available()

    def _check_docker_available(self) -> bool:
        """Проверка доступности Docker"""
        try:
            self.client = docker.from_env(timeout=self.timeout)
            # Проверяем подключение
            self.client.ping()
            logger.debug("Docker доступен")
            return True
        except DockerException as e:
            logger.warning(f"Docker недоступен: {e}")
            self.client = None
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке Docker: {e}")
            self.client = None
            return False

    def get_containers(self, all_containers: bool = False) -> List[Dict]:
        """
        Получение списка контейнеров

        Args:
            all_containers: Если True, возвращает все контейнеры (включая остановленные)

        Returns:
            Список словарей с информацией о контейнерах (совместимый с предыдущей версией)
        """
        if not self.client:
            logger.warning("Docker client не инициализирован")
            return []

        try:
            logger.debug(f"Получение списка контейнеров (all={all_containers})")
            containers = self.client.containers.list(all=all_containers)

            result = []
            for container in containers:
                # Формируем данные в формате, совместимом со старой реализацией
                container_data = {
                    'ID': container.id,
                    'Names': container.name,
                    'Image': container.image.tags[0] if container.image.tags else container.image.id,
                    'Status': container.status,
                    'State': container.attrs['State']['Status'],
                    'Ports': self._format_ports(container.ports),
                    # Сохраняем ссылку на объект контейнера для дальнейшего использования
                    '_container_obj': container
                }
                result.append(container_data)

            logger.info(f"Получено {len(result)} контейнеров")
            return result

        except APIError as e:
            logger.error(f"Ошибка API Docker при получении списка контейнеров: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении контейнеров: {e}")
            return []

    def _format_ports(self, ports: Dict) -> str:
        """
        Форматирование портов в строку, совместимую со старым форматом CLI

        Args:
            ports: Словарь портов от docker-py

        Returns:
            Строка вида "0.0.0.0:8080->8080/tcp" или пустая строка
        """
        if not ports:
            return ""

        port_strings = []
        for container_port, host_bindings in ports.items():
            if host_bindings:
                for binding in host_bindings:
                    host_ip = binding.get('HostIp', '0.0.0.0')
                    host_port = binding.get('HostPort', '')
                    if host_port:
                        port_strings.append(f"{host_ip}:{host_port}->{container_port}")
            else:
                # Порт открыт в контейнере, но не пробрасывается на хост
                port_strings.append(container_port)

        return ', '.join(port_strings)

    def get_container_inspect(self, container_id: str) -> Optional[Dict]:
        """
        Получение детальной информации о контейнере

        Args:
            container_id: ID или имя контейнера

        Returns:
            Словарь с полной информацией о контейнере или None
        """
        if not self.client:
            logger.warning("Docker client не инициализирован")
            return None

        try:
            logger.debug(f"Инспектирование контейнера: {container_id}")
            container = self.client.containers.get(container_id)
            return container.attrs

        except NotFound:
            logger.warning(f"Контейнер {container_id} не найден")
            return None
        except APIError as e:
            logger.error(f"Ошибка API Docker при инспектировании контейнера {container_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при инспектировании контейнера {container_id}: {e}")
            return None

    def get_container_compose_dir(self, container_id: str) -> Optional[str]:
        """
        Получение пути к docker-compose директории контейнера

        Args:
            container_id: ID или имя контейнера

        Returns:
            Путь к директории docker-compose или None
        """
        if not self.client:
            logger.warning("Docker client не инициализирован")
            return None

        try:
            logger.debug(f"Получение docker-compose пути для контейнера: {container_id}")
            container = self.client.containers.get(container_id)

            # Получаем label с путем к compose файлу
            labels = container.labels
            compose_path = labels.get('com.docker.compose.project.config_files')

            if not compose_path:
                logger.debug(f"Не найден docker-compose путь для {container_id}")
                return None

            # Если это файл, берем директорию
            if os.path.isfile(compose_path):
                compose_dir = os.path.dirname(compose_path)
            else:
                compose_dir = compose_path

            logger.debug(f"Docker-compose директория для {container_id}: {compose_dir}")
            return compose_dir

        except NotFound:
            logger.debug(f"Контейнер {container_id} не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении docker-compose пути для {container_id}: {e}")
            return None

    def parse_port_mapping(self, ports_string: str) -> Optional[int]:
        """
        Парсинг строки с маппингом портов Docker

        Args:
            ports_string: Строка вида "0.0.0.0:8080->8080/tcp" или "8080/tcp"

        Returns:
            Host порт или None
        """
        if not ports_string:
            return None

        try:
            # Может быть несколько маппингов через запятую
            mappings = ports_string.split(', ')
            if not mappings:
                return None

            # Берем первый маппинг
            mapping = mappings[0]

            # Проверяем есть ли маппинг на хост
            if '->' in mapping:
                # Формат: "0.0.0.0:8080->8080/tcp"
                host_part = mapping.split('->')[0]
                if ':' in host_part:
                    # Есть указание IP, берем порт после ':'
                    port_str = host_part.split(':')[-1]
                else:
                    # Только порт
                    port_str = host_part

                port = int(port_str)
                logger.debug(f"Извлечен порт {port} из маппинга {ports_string}")
                return port
            else:
                # Формат: "8080/tcp" - контейнер порт без маппинга на хост
                logger.debug(f"Нет маппинга на хост для {ports_string}")
                return None

        except (ValueError, IndexError) as e:
            logger.warning(f"Ошибка парсинга порта из {ports_string}: {e}")
            return None

    def get_container_pid(self, container_id: str) -> Optional[int]:
        """
        Получение PID главного процесса контейнера

        Args:
            container_id: ID или имя контейнера

        Returns:
            PID процесса или None
        """
        if not self.client:
            logger.warning("Docker client не инициализирован")
            return None

        try:
            logger.debug(f"Получение PID для контейнера: {container_id}")
            container = self.client.containers.get(container_id)

            # Получаем PID из attrs
            pid = container.attrs['State']['Pid']

            if not pid or pid == 0:
                logger.debug(f"Контейнер {container_id} не запущен (PID=0)")
                return None

            logger.debug(f"PID для {container_id}: {pid}")
            return pid

        except NotFound:
            logger.warning(f"Контейнер {container_id} не найден")
            return None
        except KeyError:
            logger.warning(f"Не удалось найти PID в attrs контейнера {container_id}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении PID для {container_id}: {e}")
            return None

    def parse_image_tag(self, image_string: str) -> Tuple[str, str]:
        """
        Разделение строки Docker образа на образ и тег

        Args:
            image_string: Строка вида "registry.example.com/app:v1.2.3" или "nginx:latest"

        Returns:
            Кортеж (образ, тег)
        """
        if not image_string:
            return ("", "")

        # Разделяем по последнему ':' чтобы правильно обработать registry с портом
        # Например: registry.example.com:5000/app:v1.2.3
        if ':' in image_string and not image_string.startswith('sha256:'):
            # Ищем последнее вхождение ':'
            last_colon = image_string.rfind(':')
            # Проверяем что после ':' не идет порт (цифры и /)
            after_colon = image_string[last_colon + 1:]
            if '/' not in after_colon and not after_colon.isdigit():
                # Это тег
                image = image_string[:last_colon]
                tag = after_colon
            else:
                # Это порт registry или нет тега
                image = image_string
                tag = "latest"
        else:
            # Нет тега
            image = image_string
            tag = "latest"

        logger.debug(f"Разобран образ: {image}, тег: {tag}")
        return (image, tag)

    def get_container_start_time(self, container_id: str) -> Optional[str]:
        """
        Получение времени запуска контейнера

        Args:
            container_id: ID или имя контейнера

        Returns:
            Время запуска в ISO формате или None
        """
        if not self.client:
            logger.warning("Docker client не инициализирован")
            return None

        try:
            logger.debug(f"Получение времени запуска для контейнера: {container_id}")
            container = self.client.containers.get(container_id)

            # Получаем время запуска из attrs
            start_time = container.attrs['State']['StartedAt']

            if not start_time or start_time == "0001-01-01T00:00:00Z":
                logger.debug(f"Контейнер {container_id} не был запущен")
                return None

            logger.debug(f"Время запуска для {container_id}: {start_time}")
            return start_time

        except NotFound:
            logger.warning(f"Контейнер {container_id} не найден")
            return None
        except KeyError:
            logger.warning(f"Не удалось найти StartedAt в attrs контейнера {container_id}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении времени запуска для {container_id}: {e}")
            return None


if __name__ == "__main__":
    # Тестирование клиента
    logging.basicConfig(level=logging.DEBUG)

    client = DockerClient()

    print("=== Тестирование Docker Client (docker-py) ===")

    # Получаем список контейнеров
    containers = client.get_containers()
    print(f"\nНайдено контейнеров: {len(containers)}")

    for container in containers[:3]:  # Показываем первые 3
        print(f"\nКонтейнер: {container.get('Names', 'unknown')}")
        print(f"  ID: {container.get('ID', 'unknown')}")
        print(f"  Image: {container.get('Image', 'unknown')}")
        print(f"  Status: {container.get('Status', 'unknown')}")
        print(f"  Ports: {container.get('Ports', 'unknown')}")

        # Парсим порт
        if container.get('Ports'):
            port = client.parse_port_mapping(container['Ports'])
            print(f"  Extracted Port: {port}")

        # Парсим образ
        if container.get('Image'):
            image, tag = client.parse_image_tag(container['Image'])
            print(f"  Parsed Image: {image}")
            print(f"  Parsed Tag: {tag}")

        # Получаем PID через объект контейнера (быстро)
        container_obj = container.get('_container_obj')
        if container_obj:
            pid = container_obj.attrs['State'].get('Pid')
            start_time = container_obj.attrs['State'].get('StartedAt')
            print(f"  PID (fast): {pid}")
            print(f"  Start Time (fast): {start_time}")
