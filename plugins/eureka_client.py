#!/usr/bin/env python3
"""
Eureka Client - низкоуровневый клиент для взаимодействия с Eureka
Версия: 1.0
"""

import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class EurekaClient:
    """Низкоуровневый клиент для работы с Eureka REST API"""

    def __init__(self, host: str, port: int, timeout: int = 10):
        """
        Инициализация Eureka клиента

        Args:
            host: Хост Eureka сервера
            port: Порт Eureka сервера
            timeout: Таймаут для HTTP запросов в секундах
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        logger.debug(f"Инициализирован EurekaClient для {self.base_url}")

    def get_applications(self) -> List[Dict]:
        """
        Получение списка всех приложений из Eureka

        Returns:
            Список словарей с информацией о приложениях
        """
        url = f"{self.base_url}/eureka/apps"
        logger.debug(f"Запрос приложений из Eureka: {url}")

        # Указываем что хотим получить JSON
        headers = {
            "Accept": "application/json"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            applications = []

            # Парсим структуру ответа Eureka
            if "applications" in data and "application" in data["applications"]:
                app_list = data["applications"]["application"]

                # Eureka может вернуть как список, так и один объект
                if not isinstance(app_list, list):
                    app_list = [app_list]

                for app in app_list:
                    app_name = app.get("name", "")

                    # Получаем инстансы приложения
                    instances = app.get("instance", [])
                    if not isinstance(instances, list):
                        instances = [instances]

                    for instance in instances:
                        # Извлекаем информацию об инстансе
                        instance_info = self._parse_instance(instance, app_name)
                        if instance_info:
                            applications.append(instance_info)

            logger.info(f"Получено {len(applications)} приложений из Eureka")
            return applications

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при запросе к Eureka {url}")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка соединения с Eureka {url}: {e}")
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка от Eureka: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к Eureka: {e}")
            return []

    def _parse_instance(self, instance: Dict, app_name: str) -> Optional[Dict]:
        """
        Парсинг информации об инстансе приложения

        Args:
            instance: Словарь с данными инстанса от Eureka
            app_name: Имя приложения

        Returns:
            Словарь с информацией об инстансе или None
        """
        try:
            # Извлекаем instanceId
            instance_id = instance.get("instanceId", "")

            # Извлекаем IP адрес
            # В instanceId может быть IP вместо hostname (в случае с Docker)
            ip_addr = self._extract_ip_from_instance(instance)

            # Извлекаем порт
            port = self._extract_port(instance)

            # Извлекаем URL домашней страницы
            home_page_url = instance.get("homePageUrl", "")

            # Извлекаем статус
            status = instance.get("status", "UNKNOWN")

            # Извлекаем дополнительные метаданные
            metadata = instance.get("metadata", {})

            # VIP адреса (виртуальные IP для балансировки)
            vip_address = instance.get("vipAddress", "")
            secure_vip_address = instance.get("secureVipAddress", "")

            # Информация о здоровье
            health_check_url = instance.get("healthCheckUrl", "")
            status_page_url = instance.get("statusPageUrl", "")

            return {
                "app_name": app_name,
                "instance_id": instance_id,
                "ip": ip_addr,
                "port": port,
                "home_page_url": home_page_url,
                "status": status,
                "vip_address": vip_address,
                "secure_vip_address": secure_vip_address,
                "health_check_url": health_check_url,
                "status_page_url": status_page_url,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Ошибка парсинга инстанса {instance}: {e}")
            return None

    def _extract_ip_from_instance(self, instance: Dict) -> str:
        """
        Извлечение IP адреса из данных инстанса

        Eureka может хранить IP в разных местах:
        1. В instanceId (для Docker контейнеров)
        2. В поле ipAddr

        Args:
            instance: Данные инстанса

        Returns:
            IP адрес или пустая строка
        """
        # Сначала проверяем instanceId на наличие IP
        instance_id = instance.get("instanceId", "")
        if instance_id and ":" in instance_id:
            parts = instance_id.split(":")
            if len(parts) >= 2:
                potential_ip = parts[0]
                # Проверяем, похоже ли это на IP адрес
                if self._is_valid_ip(potential_ip):
                    return potential_ip

        # Если в instanceId нет IP, берем из ipAddr
        return instance.get("ipAddr", "")

    def _is_valid_ip(self, ip_string: str) -> bool:
        """
        Проверка, является ли строка валидным IP адресом

        Args:
            ip_string: Строка для проверки

        Returns:
            True если это валидный IP адрес
        """
        try:
            parts = ip_string.split(".")
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except (ValueError, AttributeError):
            return False

    def _extract_port(self, instance: Dict) -> int:
        """
        Извлечение порта из данных инстанса

        Eureka может хранить порт как:
        1. Число
        2. Словарь {"$": порт}

        Args:
            instance: Данные инстанса

        Returns:
            Номер порта или 0
        """
        port_data = instance.get("port")

        if port_data is None:
            return 0

        if isinstance(port_data, int):
            return port_data

        if isinstance(port_data, dict):
            # Формат {"$": 8080, "@enabled": "true"}
            return int(port_data.get("$", 0))

        try:
            return int(port_data)
        except (ValueError, TypeError):
            logger.warning(f"Не удалось извлечь порт из {port_data}")
            return 0


if __name__ == "__main__":
    # Тестирование клиента
    logging.basicConfig(level=logging.DEBUG)

    # Создаем клиент (замените на реальные параметры)
    client = EurekaClient(
        host="fdse.f.ftc.ru",
        port=8761,
        timeout=10
    )

    print("=== Тестирование Eureka Client ===")

    # Получаем список приложений
    apps = client.get_applications()
    print(f"\nНайдено приложений в Eureka: {len(apps)}")

    # Показываем первые 3 приложения
    for app in apps[:3]:
        print(f"\nПриложение: {app['app_name']}")
        print(f"  Instance ID: {app['instance_id']}")
        print(f"  IP: {app['ip']}")
        print(f"  Port: {app['port']}")
        print(f"  Status: {app['status']}")
        print(f"  Home Page: {app['home_page_url']}")
        if app['metadata']:
            print(f"  Metadata: {app['metadata']}")