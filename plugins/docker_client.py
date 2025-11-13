#!/usr/bin/env python3
"""
Docker Client - низкоуровневый клиент для взаимодействия с Docker CLI
Версия: 1.0
"""

import subprocess
import json
import logging
import os
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class DockerClient:
    """Низкоуровневый клиент для работы с Docker через CLI"""

    def __init__(self, timeout: int = 10):
        """
        Инициализация Docker клиента

        Args:
            timeout: Таймаут для выполнения команд в секундах
        """
        self.timeout = timeout
        self._check_docker_available()

    def _check_docker_available(self) -> bool:
        """Проверка доступности Docker"""
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning(f"Docker недоступен: {result.stderr}")
                return False
            logger.debug("Docker доступен")
            return True
        except FileNotFoundError:
            logger.warning("Docker не установлен")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Таймаут при проверке Docker")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке Docker: {e}")
            return False

    def get_containers(self, all_containers: bool = False) -> List[Dict]:
        """
        Получение списка контейнеров

        Args:
            all_containers: Если True, возвращает все контейнеры (включая остановленные)

        Returns:
            Список словарей с информацией о контейнерах
        """
        cmd = ["docker", "ps", "--format", "{{json .}}"]
        if all_containers:
            cmd.insert(2, "-a")

        try:
            logger.debug(f"Выполнение команды: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.error(f"Ошибка при получении списка контейнеров: {result.stderr}")
                return []

            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        container = json.loads(line)
                        containers.append(container)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Ошибка парсинга JSON для контейнера: {e}")
                        continue

            logger.info(f"Получено {len(containers)} контейнеров")
            return containers

        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при получении списка контейнеров")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении контейнеров: {e}")
            return []

    def get_container_inspect(self, container_id: str) -> Optional[Dict]:
        """
        Получение детальной информации о контейнере

        Args:
            container_id: ID или имя контейнера

        Returns:
            Словарь с полной информацией о контейнере или None
        """
        cmd = ["docker", "inspect", container_id]

        try:
            logger.debug(f"Инспектирование контейнера: {container_id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.warning(f"Ошибка при инспектировании контейнера {container_id}: {result.stderr}")
                return None

            data = json.loads(result.stdout)
            if data and isinstance(data, list):
                return data[0]
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON для контейнера {container_id}: {e}")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при инспектировании контейнера {container_id}")
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
        cmd = [
            "docker", "inspect",
            "--format", "{{ index .Config.Labels \"com.docker.compose.project.config_files\"}}",
            container_id
        ]

        try:
            logger.debug(f"Получение docker-compose пути для контейнера: {container_id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.debug(f"Не найден docker-compose путь для {container_id}")
                return None

            compose_path = result.stdout.strip()
            if not compose_path or compose_path == "<no value>":
                return None

            # Если это файл, берем директорию
            if os.path.isfile(compose_path):
                compose_dir = os.path.dirname(compose_path)
            else:
                compose_dir = compose_path

            logger.debug(f"Docker-compose директория для {container_id}: {compose_dir}")
            return compose_dir

        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при получении docker-compose пути для {container_id}")
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
        cmd = [
            "docker", "inspect",
            "-f", "{{.State.Pid}}",
            container_id
        ]

        try:
            logger.debug(f"Получение PID для контейнера: {container_id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.warning(f"Ошибка при получении PID для {container_id}: {result.stderr}")
                return None

            pid_str = result.stdout.strip()
            if not pid_str or pid_str == "0":
                logger.debug(f"Контейнер {container_id} не запущен (PID=0)")
                return None

            pid = int(pid_str)
            logger.debug(f"PID для {container_id}: {pid}")
            return pid

        except ValueError as e:
            logger.warning(f"Ошибка преобразования PID для {container_id}: {e}")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при получении PID для {container_id}")
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
        cmd = [
            "docker", "inspect",
            "-f", "{{.State.StartedAt}}",
            container_id
        ]

        try:
            logger.debug(f"Получение времени запуска для контейнера: {container_id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                logger.warning(f"Ошибка при получении времени запуска для {container_id}: {result.stderr}")
                return None

            start_time = result.stdout.strip()
            if not start_time or start_time == "0001-01-01T00:00:00Z":
                logger.debug(f"Контейнер {container_id} не был запущен")
                return None

            logger.debug(f"Время запуска для {container_id}: {start_time}")
            return start_time

        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при получении времени запуска для {container_id}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении времени запуска для {container_id}: {e}")
            return None


if __name__ == "__main__":
    # Тестирование клиента
    logging.basicConfig(level=logging.DEBUG)

    client = DockerClient()

    print("=== Тестирование Docker Client ===")

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