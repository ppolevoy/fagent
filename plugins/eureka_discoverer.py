#!/usr/bin/env python3
"""
Eureka Discoverer - Независимый plugin для обнаружения приложений в Eureka
Версия: 1.0
"""

import logging
from typing import List

from discovery import AbstractDiscoverer
from models import ApplicationInfo
from plugins.eureka_client import EurekaClient
import config

logger = logging.getLogger(__name__)


class EurekaDiscoverer(AbstractDiscoverer):
    """Plugin для обнаружения приложений, зарегистрированных в Eureka"""

    def __init__(self):
        """Инициализация Eureka discoverer"""
        super().__init__()
        self.enabled = getattr(config, 'EUREKA_DISCOVERY_ENABLED', False)

        if self.enabled:
            try:
                self.host = getattr(config, 'EUREKA_HOST', 'fdse.f.ftc.ru')
                self.port = getattr(config, 'EUREKA_PORT', 8761)
                self.timeout = getattr(config, 'EUREKA_REQUEST_TIMEOUT', 10)

                self.client = EurekaClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout
                )
                logger.info(f"Eureka discoverer инициализирован (host={self.host}, port={self.port})")
            except Exception as e:
                logger.error(f"Ошибка инициализации Eureka client: {e}")
                self.enabled = False
                self.client = None
        else:
            logger.info("Eureka discoverer отключен в конфигурации")
            self.client = None

    def _extract_version_from_metadata(self, metadata: dict) -> str:
        """
        Попытка извлечь версию из метаданных Eureka

        Args:
            metadata: Словарь метаданных от Eureka

        Returns:
            Версия или "unknown"
        """
        if not metadata:
            return "unknown"

        # Ищем версию в разных возможных полях метаданных
        version_fields = [
            "version",
            "app.version",
            "application.version",
            "build.version",
            "implementation.version"
        ]

        for field in version_fields:
            if field in metadata:
                return str(metadata[field])

        return "unknown"

    def _map_eureka_status(self, eureka_status: str) -> str:
        """
        Преобразование статуса Eureka в статус ApplicationInfo

        Args:
            eureka_status: Статус из Eureka (UP, DOWN, etc.)

        Returns:
            Статус для ApplicationInfo
        """
        status_mapping = {
            "UP": "online",
            "DOWN": "offline",
            "STARTING": "starting",
            "OUT_OF_SERVICE": "maintenance",
            "UNKNOWN": "unknown"
        }

        eureka_status_upper = eureka_status.upper() if eureka_status else "UNKNOWN"
        return status_mapping.get(eureka_status_upper, "unknown")

    def discover(self) -> List[ApplicationInfo]:
        """
        Обнаружение приложений в Eureka

        Returns:
            Список ApplicationInfo для найденных приложений
        """
        if not self.enabled or not self.client:
            logger.debug("Eureka discoverer отключен или не инициализирован")
            return []

        applications = []

        try:
            # Получаем список приложений из Eureka
            eureka_apps = self.client.get_applications()

            if not eureka_apps:
                logger.info("Приложения в Eureka не найдены")
                return []

            for eureka_app in eureka_apps:
                try:
                    # Извлекаем информацию из ответа Eureka
                    app_name = eureka_app.get('app_name', 'unknown')
                    instance_id = eureka_app.get('instance_id', '')
                    ip_addr = eureka_app.get('ip', '')
                    port = eureka_app.get('port', 0)
                    status = eureka_app.get('status', 'UNKNOWN')
                    home_page_url = eureka_app.get('home_page_url', '')
                    metadata = eureka_app.get('metadata', {})

                    # Извлекаем версию из метаданных если есть
                    version = self._extract_version_from_metadata(metadata)

                    # Преобразуем статус
                    app_status = self._map_eureka_status(status)

                    # Создаем ApplicationInfo
                    app_info = ApplicationInfo(
                        name=app_name,
                        version=version,
                        status=app_status,
                        start_time="unknown",  # Eureka не предоставляет время запуска
                        metadata={
                            "source": "eureka",
                            "instance_id": instance_id,
                            "ip": ip_addr,
                            "port": port if port else None,
                            "home_page_url": home_page_url,
                            "eureka_status": status,
                            "vip_address": eureka_app.get('vip_address', ''),
                            "secure_vip_address": eureka_app.get('secure_vip_address', ''),
                            "health_check_url": eureka_app.get('health_check_url', ''),
                            "status_page_url": eureka_app.get('status_page_url', ''),
                            "eureka_metadata": metadata
                        }
                    )

                    applications.append(app_info)
                    logger.debug(f"Обнаружено приложение в Eureka: {app_name} ({instance_id})")

                except Exception as e:
                    logger.error(f"Ошибка обработки приложения из Eureka {eureka_app}: {e}")
                    continue

            logger.info(f"Eureka discoverer обнаружил {len(applications)} приложений")

        except Exception as e:
            logger.error(f"Критическая ошибка в Eureka discoverer: {e}")

        return applications


if __name__ == "__main__":
    # Тестирование discoverer
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Включаем Eureka discovery для теста
    config.EUREKA_DISCOVERY_ENABLED = True
    config.EUREKA_HOST = "fdse.f.ftc.ru"
    config.EUREKA_PORT = 8761
    config.EUREKA_REQUEST_TIMEOUT = 10

    discoverer = EurekaDiscoverer()
    apps = discoverer.discover()

    print(f"\n=== Найдено Eureka приложений: {len(apps)} ===\n")

    for app in apps[:5]:  # Показываем первые 5
        print(f"Приложение: {app.name}")
        print(f"  Версия: {app.version}")
        print(f"  Статус: {app.status}")
        print(f"  Время запуска: {app.start_time}")
        print(f"  Метаданные:")
        for key, value in app.metadata.items():
            if value and key != "eureka_metadata":  # Не выводим вложенные метаданные
                print(f"    {key}: {value}")
        print()