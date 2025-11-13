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
        1. В instanceId (для Docker контейнеров) - приоритет!
        2. В поле ipAddr

        Важно: Для Docker контейнеров instanceId часто содержит реальный IP (host IP),
        в то время как ipAddr может содержать внутренний Docker IP (172.17.x.x).

        Args:
            instance: Данные инстанса

        Returns:
            IP адрес или пустая строка
        """
        # Сначала проверяем instanceId на наличие IP (приоритет для Docker)
        instance_id = instance.get("instanceId", "")
        if instance_id and ":" in instance_id:
            parts = instance_id.split(":")
            if len(parts) >= 2:
                potential_ip = parts[0]
                # Проверяем, похоже ли это на IP адрес
                if self._is_valid_ip(potential_ip):
                    logger.debug(f"Извлечен IP из instanceId: {potential_ip}")
                    return potential_ip

        # Если в instanceId нет IP, берем из ipAddr
        ip_addr = instance.get("ipAddr", "")
        if ip_addr:
            logger.debug(f"Использован IP из ipAddr: {ip_addr}")
        return ip_addr

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

    def check_app_health(self, home_page_url: str) -> Dict:
        """
        Проверка здоровья приложения через /actuator/health

        Args:
            home_page_url: URL домашней страницы приложения

        Returns:
            Словарь с результатом проверки
        """
        if not home_page_url:
            return {
                "status": "error",
                "message": "No home_page_url provided"
            }

        health_url = f"{home_page_url.rstrip('/')}/actuator/health"
        logger.debug(f"Проверка здоровья: {health_url}")

        try:
            response = requests.get(health_url, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    health_data = response.json()
                    return {
                        "status": "healthy",
                        "http_status": response.status_code,
                        "health_status": health_data.get("status", "UNKNOWN"),
                        "details": health_data
                    }
                except ValueError:
                    return {
                        "status": "responding",
                        "http_status": response.status_code,
                        "message": "Application responding but no JSON health data"
                    }
            else:
                return {
                    "status": "unhealthy",
                    "http_status": response.status_code,
                    "message": f"Health check returned HTTP {response.status_code}"
                }

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при проверке здоровья: {health_url}")
            return {
                "status": "timeout",
                "message": f"Health check timeout after {self.timeout}s"
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка подключения при проверке здоровья: {e}")
            return {
                "status": "unreachable",
                "message": f"Cannot connect to application: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке здоровья: {e}")
            return {
                "status": "error",
                "message": f"Health check error: {str(e)}"
            }

    def shutdown_app(self, home_page_url: str) -> Dict:
        """
        Graceful shutdown приложения через /actuator/shutdown

        Args:
            home_page_url: URL домашней страницы приложения

        Returns:
            Словарь с результатом операции
        """
        if not home_page_url:
            return {
                "success": False,
                "message": "No home_page_url provided"
            }

        shutdown_url = f"{home_page_url.rstrip('/')}/actuator/shutdown"
        logger.info(f"Отправка запроса shutdown: {shutdown_url}")

        try:
            response = requests.post(shutdown_url, timeout=self.timeout)

            if response.status_code in (200, 202):
                try:
                    response_data = response.json()
                    return {
                        "success": True,
                        "message": "Shutdown request sent successfully",
                        "http_status": response.status_code,
                        "details": response_data
                    }
                except ValueError:
                    return {
                        "success": True,
                        "message": "Shutdown request sent successfully",
                        "http_status": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "http_status": response.status_code,
                    "message": f"Shutdown request failed: HTTP {response.status_code}",
                    "response": response.text
                }

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при отправке shutdown: {shutdown_url}")
            return {
                "success": False,
                "message": f"Shutdown request timeout after {self.timeout}s"
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка подключения при shutdown: {e}")
            return {
                "success": False,
                "message": f"Cannot connect to application: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Ошибка при shutdown: {e}")
            return {
                "success": False,
                "message": f"Shutdown error: {str(e)}"
            }

    def find_app_by_ip_port(self, ip: str, port: int) -> Optional[Dict]:
        """
        Найти приложение в Eureka по IP и порту.

        Используется для сопоставления Docker контейнеров с Eureka регистрацией.

        Args:
            ip: IP адрес приложения
            port: Порт приложения

        Returns:
            Словарь с данными приложения или None если не найдено
        """
        try:
            apps = self.get_applications()

            for app in apps:
                app_ip = app.get("ip", "")
                app_port = app.get("port", 0)

                if app_ip == ip and app_port == port:
                    logger.debug(f"Найдено совпадение в Eureka: {ip}:{port} -> {app.get('instance_id')}")
                    return app

            logger.debug(f"Приложение {ip}:{port} не найдено в Eureka")
            return None

        except Exception as e:
            logger.error(f"Ошибка поиска приложения в Eureka по {ip}:{port}: {e}")
            return None

    def pause_app(self, home_page_url: str) -> Dict:
        """
        Pause приложения через /actuator/pause

        Args:
            home_page_url: URL домашней страницы приложения

        Returns:
            Словарь с результатом операции
        """
        if not home_page_url:
            return {
                "success": False,
                "message": "No home_page_url provided"
            }

        pause_url = f"{home_page_url.rstrip('/')}/actuator/pause"
        logger.info(f"Отправка запроса pause: {pause_url}")

        try:
            response = requests.post(pause_url, timeout=self.timeout)

            if response.status_code in (200, 202, 204):
                try:
                    response_data = response.json()
                    return {
                        "success": True,
                        "message": "Pause request sent successfully",
                        "http_status": response.status_code,
                        "details": response_data
                    }
                except ValueError:
                    # Нет JSON в ответе
                    return {
                        "success": True,
                        "message": "Pause request sent successfully",
                        "http_status": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "http_status": response.status_code,
                    "message": f"Pause request failed: HTTP {response.status_code}",
                    "response": response.text
                }

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при отправке pause: {pause_url}")
            return {
                "success": False,
                "message": f"Pause request timeout after {self.timeout}s"
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка подключения при pause: {e}")
            return {
                "success": False,
                "message": f"Cannot connect to application: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Ошибка при pause: {e}")
            return {
                "success": False,
                "message": f"Pause error: {str(e)}"
            }

    def set_app_loglevel(self, home_page_url: str, logger_name: str, level: str) -> Dict:
        """
        Изменение уровня логирования приложения через /actuator/loggers

        Args:
            home_page_url: URL домашней страницы приложения
            logger_name: Имя логгера (например, "com.example.myapp" или "ROOT")
            level: Уровень логирования (TRACE, DEBUG, INFO, WARN, ERROR, OFF)

        Returns:
            Словарь с результатом операции
        """
        if not home_page_url:
            return {
                "success": False,
                "message": "No home_page_url provided"
            }

        valid_levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "OFF"]
        level_upper = level.upper()

        if level_upper not in valid_levels:
            return {
                "success": False,
                "message": f"Invalid log level '{level}'. Must be one of: {', '.join(valid_levels)}"
            }

        loggers_url = f"{home_page_url.rstrip('/')}/actuator/loggers/{logger_name}"
        logger.info(f"Изменение уровня логирования {logger_name} на {level_upper}: {loggers_url}")

        try:
            payload = {"configuredLevel": level_upper}
            headers = {"Content-Type": "application/json"}

            response = requests.post(loggers_url, json=payload, headers=headers, timeout=self.timeout)

            if response.status_code in (200, 204):
                return {
                    "success": True,
                    "message": f"Log level for '{logger_name}' changed to {level_upper}",
                    "http_status": response.status_code
                }
            else:
                return {
                    "success": False,
                    "http_status": response.status_code,
                    "message": f"Failed to change log level: HTTP {response.status_code}",
                    "response": response.text
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": f"Request timeout after {self.timeout}s"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "message": f"Cannot connect to application: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error changing log level: {str(e)}"
            }


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