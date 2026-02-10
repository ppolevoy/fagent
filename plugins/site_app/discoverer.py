# plugins/site_app/discoverer.py
"""
Основной модуль обнаружения site-app приложений.

Поддерживает:
- Solaris: svcs (SMF)
- Linux: systemd или pgrep
"""
import re
import sys
import logging
import json
import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from discovery import AbstractDiscoverer
from models import ApplicationInfo
from config import Config
from .shell_executor import ShellExecutor
from .platforms import create_process_manager

logger = logging.getLogger(__name__)

class SiteAppDiscoverer(AbstractDiscoverer):
    """Плагин для обнаружения приложений в структуре /site/app (Solaris svcs / Linux systemd/process)."""

    ARTIFACT_CHECK_ORDER = ['war', 'jar', 'dir']

    def __init__(self):
        """Инициализация плагина с проверкой конфигурации"""
        super().__init__()

        # Определяем платформу
        self.platform = self._detect_platform()

        # Проверяем включен ли плагин
        self.enabled = getattr(Config, 'SITE_DISCOVERY_ENABLED', True)

        # Режим работы на Linux
        self.process_manager = getattr(Config, 'SITE_PROCESS_MANAGER', 'process')
        self.systemd_pattern = getattr(Config, 'SITE_SYSTEMD_SERVICE_PATTERN', '{app_name}')
        self.pgrep_pattern = getattr(Config, 'SITE_PGREP_PATTERN', 'java.*{app_name}')

        # Таймаут для subprocess вызовов
        self.subprocess_timeout = getattr(Config, 'SITE_SUBPROCESS_TIMEOUT', 10)

        # Количество параллельных потоков для сканирования
        self.discovery_workers = getattr(Config, 'SITE_DISCOVERY_WORKERS', 4)

        # ShellExecutor для централизованного выполнения команд
        self.shell = ShellExecutor(timeout=self.subprocess_timeout, retries=1)

        # ProcessManager через фабрику (Strategy pattern)
        self.process_manager_impl = create_process_manager(
            platform=self.platform,
            mode=self.process_manager,
            shell=self.shell,
            systemd_pattern=self.systemd_pattern,
            pgrep_pattern=self.pgrep_pattern
        )

        self.app_root = Config.SITE_APP_ROOT
        self.htdoc_root = Config.SITE_HTPDOC_ROOT

        # Получаем список поддерживаемых расширений из конфигурации
        self.supported_extensions = getattr(
            Config,
            'SUPPORTED_ARTIFACT_EXTENSIONS',
            ['jar', 'war']
        )

        # Загружаем маппинг имен приложений
        self.name_mapping = self._load_name_mapping()

        # Определяем режим работы для логирования
        if self.platform == 'solaris':
            mode = 'svcs'
        else:
            mode = self.process_manager

        logger.info(
            f"SiteAppDiscoverer инициализирован. "
            f"Платформа: {self.platform}, Режим: {mode}, "
            f"Поддерживаемые расширения: {', '.join(self.supported_extensions)}"
        )

        if self.name_mapping:
            logger.info(f"Загружен маппинг для {len(self.name_mapping)} приложений")

        # Кэш портов для оптимизации (заполняется один раз за discover())
        self._cached_ports = None

        # Проверяем доступность директорий
        self._validate_paths()

    def _detect_platform(self) -> str:
        """
        Определяет платформу выполнения.

        Returns:
            str: 'solaris' или 'linux'
        """
        if sys.platform.startswith('sunos'):
            return 'solaris'
        return 'linux'

    def _validate_paths(self) -> None:
        """Проверка существования необходимых директорий"""
        if not self.app_root.exists():
            logger.warning(f"Директория приложений не существует: {self.app_root}")

        if not self.htdoc_root.exists():
            logger.warning(f"Директория дистрибутивов не существует: {self.htdoc_root}")

    def _load_name_mapping(self) -> Dict[str, str]:
        """
        Загрузка маппинга имен приложений из JSON файла.

        Формат файла:
        {
            "app_name": "htdoc_name",
            "doc-print": "document-printable"
        }

        Returns:
            Dict[str, str]: Словарь маппинга имен или пустой словарь
        """
        mapping_file = getattr(Config, 'APP_NAME_MAPPING_FILE', None)

        if not mapping_file:
            logger.debug("Путь к файлу маппинга не задан в конфигурации")
            return {}

        if not mapping_file.exists():
            logger.debug(f"Файл маппинга не найден: {mapping_file}")
            return {}

        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping = json.load(f)

            if not isinstance(mapping, dict):
                logger.warning(f"Некорректный формат файла маппинга: ожидается словарь")
                return {}

            logger.info(f"Загружен маппинг из {mapping_file}: {mapping}")
            return mapping

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в {mapping_file}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке маппинга из {mapping_file}: {e}")

        return {}

    # ==================== Публичные методы ====================

    def _get_app_status(self, app_name: str) -> Tuple[str, str]:
        """
        Получение статуса через ProcessManager (Strategy pattern).

        Args:
            app_name: Имя приложения

        Returns:
            Tuple[str, str]: (статус, время_запуска)
        """
        return self.process_manager_impl.get_status(app_name)

    def _get_app_pid(self, app_name: str) -> Optional[int]:
        """
        Получение PID через ProcessManager (Strategy pattern).

        Args:
            app_name: Имя приложения

        Returns:
            Optional[int]: PID процесса или None
        """
        return self.process_manager_impl.get_pid(app_name)

    def _parse_tomcat_server_xml(self, app_name: str) -> Optional[int]:
        """
        Парсинг server.xml для получения HTTP порта Tomcat.

        Args:
            app_name: Имя приложения

        Returns:
            Optional[int]: HTTP порт из server.xml или None
        """
        # Путь к server.xml в структуре приложения
        server_xml_path = self.app_root / app_name / "conf" / "server.xml"

        if not server_xml_path.exists():
            logger.debug(f"{app_name}: server.xml не найден по пути {server_xml_path}")
            return None

        try:
            with open(server_xml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Ищем HTTP Connector с портом
            # <Connector port="8080" protocol="HTTP/1.1" .../>
            # Игнорируем комментарии и AJP коннекторы
            # Удаляем XML комментарии
            content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

            # Ищем HTTP/1.1 Connector (не AJP)
            connector_pattern = r'<Connector[^>]*port=["\'](\d+)["\'][^>]*protocol=["\']HTTP'
            match = re.search(connector_pattern, content, re.IGNORECASE)

            if match:
                port = int(match.group(1))
                logger.debug(f"{app_name}: найден HTTP порт {port} в server.xml")
                return port
            else:
                logger.debug(f"{app_name}: HTTP Connector не найден в server.xml")

        except Exception as e:
            logger.warning(f"{app_name}: ошибка при чтении server.xml: {e}")

        return None

    def _get_listening_ports_netstat(self) -> Dict[int, int]:
        """
        Получение списка всех портов в состоянии LISTEN.

        На Solaris использует netstat -an -P tcp.
        На Linux использует ss -tlnp.

        Returns:
            Dict[int, int]: Словарь {порт: pid} (pid может быть 0, если не удалось определить)
        """
        ports = {}

        if self.platform == 'solaris':
            # Solaris: netstat -an -P tcp
            result = self.shell.run(["netstat", "-an", "-P", "tcp"])

            if result.success and result.stdout:
                for line in result.stdout.split('\n'):
                    if 'LISTEN' in line:
                        parts = line.split()
                        if len(parts) >= 1:
                            local_addr = parts[0]
                            port_match = re.search(r'[.*](\d+)$', local_addr)
                            if port_match:
                                port = int(port_match.group(1))
                                ports[port] = 0
        else:
            # Linux: ss -tlnp (предпочтительно)
            result = self.shell.run(["ss", "-tlnp"])

            if result.success and result.stdout:
                # Пропускаем заголовок
                for line in result.stdout.split('\n')[1:]:
                    if not line.strip():
                        continue
                    # Формат: State  Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
                    # LISTEN  0  128  *:8080  *:*  users:(("java",pid=1234,fd=5))
                    parts = line.split()
                    if len(parts) >= 4:
                        local_addr = parts[3]
                        # Извлекаем порт: *:8080 или 0.0.0.0:8080 или [::]:8080
                        if ':' in local_addr:
                            port_str = local_addr.rsplit(':', 1)[1]
                            if port_str.isdigit():
                                ports[int(port_str)] = 0

        logger.debug(f"Найдено {len(ports)} портов в состоянии LISTEN")

        return ports

    def _get_app_port(self, app_name: str, pid: Optional[int]) -> Optional[int]:
        """
        Получение порта приложения.

        Использует следующие методы в порядке приоритета:
        1. Парсинг server.xml (для Tomcat)
        2. Поиск через netstat (менее надежно, так как не привязан к конкретному PID)

        Args:
            app_name: Имя приложения
            pid: PID процесса приложения

        Returns:
            Optional[int]: Порт приложения или None
        """
        # 1. Проверяем server.xml для Tomcat
        port = self._parse_tomcat_server_xml(app_name)
        if port:
            logger.debug(f"{app_name}: порт {port} определен из server.xml")
            return port

        # 2. Используем кэшированные порты как fallback
        # Внимание: этот метод не привязан к конкретному PID,
        # поэтому может быть неточным если на сервере много приложений
        logger.debug(f"{app_name}: пытаемся определить порт через кэш портов")

        # Используем кэшированные порты (если кэш пуст, получаем заново)
        listening_ports = self._cached_ports if self._cached_ports is not None else self._get_listening_ports_netstat()

        # Без server.xml невозможно точно определить порт приложения
        # Возвращаем None вместо эвристики с common_ports
        logger.debug(f"{app_name}: не удалось определить порт приложения (server.xml не найден)")
        return None

    def _find_artifact(self, app_name: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Поиск артефакта приложения (jar/war/dir).

        Использует маппинг имен, если он задан в конфигурации.
        Маппинг может содержать:
        - Относительное имя: "document-printable" -> ищет в htdoc_root
        - Абсолютный путь: "/path/to/app.war" -> использует напрямую

        Args:
            app_name: Имя приложения из app_root

        Returns:
            Tuple[Optional[Path], Optional[str]]: (путь_к_артефакту, тип_артефакта)
        """
        # Определяем имя/путь для поиска артефакта
        htdoc_name_or_path = self.name_mapping.get(app_name, app_name)

        if htdoc_name_or_path != app_name:
            logger.debug(f"{app_name}: используется маппинг -> {htdoc_name_or_path}")

        # Проверяем, является ли значение маппинга абсолютным путем
        mapped_path = Path(htdoc_name_or_path)
        if mapped_path.is_absolute():
            logger.debug(f"{app_name}: маппинг указывает на абсолютный путь {mapped_path}")

            if not mapped_path.exists():
                logger.warning(f"{app_name}: путь из маппинга не существует: {mapped_path}")
                return None, None

            # Определяем тип артефакта по пути
            if mapped_path.is_dir():
                return mapped_path, 'directory'
            elif mapped_path.is_file():
                suffix = mapped_path.suffix.lstrip('.')
                if suffix in self.supported_extensions:
                    logger.debug(f"{app_name}: найден {suffix.upper()} файл по абсолютному пути")
                    return mapped_path, suffix
                else:
                    logger.warning(f"{app_name}: неподдерживаемый тип файла: {suffix}")
                    return None, None
            else:
                logger.warning(f"{app_name}: путь не является файлом или директорией: {mapped_path}")
                return None, None

        # Относительное имя - ищем в htdoc_root
        htdoc_name = htdoc_name_or_path

        # Проверяем артефакты в порядке приоритета
        for artifact_type in self.ARTIFACT_CHECK_ORDER:
            if artifact_type == 'dir':
                # Проверяем директорию (симлинк на директорию)
                dir_symlink = self.htdoc_root / htdoc_name
                if dir_symlink.is_symlink() and dir_symlink.resolve().is_dir():
                    logger.debug(f"{app_name}: найдена директория {dir_symlink}")
                    return dir_symlink.resolve(), 'directory'
            else:
                # Проверяем файловые артефакты
                if artifact_type not in self.supported_extensions:
                    continue

                artifact_symlink = self.htdoc_root / f"{htdoc_name}.{artifact_type}"
                if artifact_symlink.is_symlink():
                    resolved_path = artifact_symlink.resolve()
                    if resolved_path.exists():
                        logger.debug(
                            f"{app_name}: найден {artifact_type.upper()} файл {artifact_symlink}"
                        )
                        return resolved_path, artifact_type
                    else:
                        logger.warning(
                            f"{app_name}: симлинк {artifact_symlink} указывает "
                            f"на несуществующий файл {resolved_path}"
                        )

        logger.debug(f"{app_name}: артефакт не найден (искали как '{htdoc_name}')")
        return None, None

    def _build_version_pattern(self) -> re.Pattern:
        """
        Создание regex pattern для извлечения версии из пути артефакта.
        
        Поддерживает форматы:
        - /path/app-1.2.3.jar
        - /path/20250101_120000_app-1.2.3/app-1.2.3.jar
        - /path/20250101_120000_app-1.2.3
        
        Returns:
            re.Pattern: Скомпилированное регулярное выражение
        """
        # Создаем pattern для расширений: (?:\.jar|\.war)?
        if self.supported_extensions:
            ext_pattern = "|".join(f"\\.{ext}" for ext in self.supported_extensions)
            ext_pattern = f"(?:{ext_pattern})?"
        else:
            ext_pattern = ""
        
        # Полный pattern
        pattern = rf"(?:\d{{8}}_\d{{6}}_[^\/+-|\/])?([\d\.]+){ext_pattern}$"
        return re.compile(pattern)
    
    def _extract_version(self, artifact_path: Path) -> str:
        """
        Извлечение версии из пути артефакта.
        
        Args:
            artifact_path: Путь к артефакту
            
        Returns:
            str: Версия приложения или сообщение об ошибке
        """
        if not artifact_path:
            return "unknown-no-artifact"
        
        pattern = self._build_version_pattern()
        match = pattern.search(str(artifact_path))
        
        if match:
            version = match.group(1)
            logger.debug(f"Извлечена версия {version} из {artifact_path}")
            return version
        else:
            logger.warning(f"Не удалось извлечь версию из {artifact_path}")
            return "unknown-no-match"
    
    def _get_artifact_metadata(
        self,
        app_name: str,
        artifact_path: Optional[Path],
        artifact_type: Optional[str],
        pid: Optional[int] = None,
        port: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Сбор метаданных об артефакте.

        Args:
            app_name: Имя приложения
            artifact_path: Путь к артефакту
            artifact_type: Тип артефакта (jar/war/directory)
            pid: PID основного процесса приложения
            port: Порт, на котором слушает приложение

        Returns:
            Dict[str, Any]: Словарь с метаданными
        """
        metadata = {}

        # PID процесса
        if pid is not None:
            metadata["pid"] = pid
        else:
            metadata["pid"] = None

        # Порт приложения
        if port is not None:
            metadata["port"] = port
        else:
            metadata["port"] = None

        # Путь к логам
        logs_path = self.app_root / app_name / "logs"
        if logs_path.is_symlink():
            metadata["log_path"] = str(logs_path.resolve())
        else:
            metadata["log_path"] = "Unknown"
        
        # Путь к дистрибутиву
        if artifact_path:
            metadata["distr_path"] = str(artifact_path)
            
            # Размер артефакта (если это файл)
            if artifact_path.is_file():
                try:
                    size_bytes = artifact_path.stat().st_size
                    metadata["artifact_size_bytes"] = size_bytes
                    metadata["artifact_size_mb"] = round(size_bytes / (1024 * 1024), 2)
                except Exception as e:
                    logger.warning(f"Не удалось получить размер файла {artifact_path}: {e}")
        else:
            metadata["distr_path"] = "Unknown"
        
        # Тип артефакта
        if artifact_type:
            metadata["artifact_type"] = artifact_type
           
        
        # Путь к приложению
        metadata["app_path"] = str(self.app_root / app_name)

        # Источник данных
        metadata["source"] = "site-app"

        return metadata

    def _process_single_app(self, name: str) -> Optional[ApplicationInfo]:
        """
        Обработка одного приложения для параллельного выполнения.

        Args:
            name: Имя приложения

        Returns:
            ApplicationInfo или None если приложение не найдено/ошибка
        """
        try:
            # ОПТИМИЗАЦИЯ: Сначала проверяем артефакт (не требует subprocess)
            artifact_path, artifact_type = self._find_artifact(name)

            # Пропускаем приложения без артефакта ДО вызова subprocess
            if not artifact_path:
                logger.debug(f"{name}: артефакт не найден, приложение пропущено")
                return None

            # Получаем статус приложения (svcs/systemd/process)
            status, start_time = self._get_app_status(name)

            # Получаем PID процесса
            pid = self._get_app_pid(name)

            # Получаем порт приложения
            port = self._get_app_port(name, pid)

            # Извлекаем версию
            version = self._extract_version(artifact_path)

            # Собираем метаданные
            metadata = self._get_artifact_metadata(name, artifact_path, artifact_type, pid, port)

            # Создаем объект приложения
            app_info = ApplicationInfo(
                name=name,
                version=version,
                status=status,
                start_time=start_time,
                metadata=metadata
            )

            logger.debug(f"Успешно обработано приложение: {name}")
            return app_info

        except Exception as e:
            logger.error(f"Ошибка при обработке приложения {name}: {e}", exc_info=True)
            return None

    def discover(self) -> List[ApplicationInfo]:
        """
        Основной метод обнаружения приложений.

        Использует ThreadPoolExecutor для параллельной обработки приложений.

        Returns:
            List[ApplicationInfo]: Список обнаруженных приложений
        """
        # Проверяем, включен ли плагин
        if not self.enabled:
            logger.info("Site App discovery отключен (SITE_DISCOVERY_ENABLED=false)")
            return []

        # Кэшируем порты один раз для всех приложений (ДО параллельного выполнения!)
        self._cached_ports = self._get_listening_ports_netstat()
        logger.debug(f"Кэшировано {len(self._cached_ports)} портов для discover()")

        # Проверяем существование директорий
        if not (self.app_root.exists() and self.htdoc_root.exists()):
            logger.error(
                f"Требуемые директории не существуют. "
                f"app_root={self.app_root}, htdoc_root={self.htdoc_root}"
            )
            return []

        apps = []

        try:
            # Получаем список приложений
            app_names = sorted([
                app_dir.name
                for app_dir in self.app_root.iterdir()
                if app_dir.is_dir()
            ])

            logger.debug(f"Обнаружено приложений в {self.app_root}: {len(app_names)}")

            # Параллельная обработка приложений
            # Общий таймаут на discovery = subprocess_timeout * количество_приложений / workers * 2
            discovery_timeout = max(
                self.subprocess_timeout * 3,
                self.subprocess_timeout * len(app_names) / self.discovery_workers * 2
            )

            with ThreadPoolExecutor(max_workers=self.discovery_workers) as executor:
                # Запускаем обработку всех приложений параллельно
                future_to_name = {
                    executor.submit(self._process_single_app, name): name
                    for name in app_names
                }

                # Собираем результаты по мере завершения с таймаутом
                try:
                    for future in as_completed(future_to_name, timeout=discovery_timeout):
                        name = future_to_name[future]
                        try:
                            result = future.result(timeout=self.subprocess_timeout)
                            if result is not None:
                                apps.append(result)
                        except FuturesTimeoutError:
                            logger.warning(f"Таймаут обработки приложения {name}")
                        except Exception as e:
                            logger.error(f"Ошибка при обработке {name}: {e}", exc_info=True)
                except FuturesTimeoutError:
                    logger.warning(
                        f"Общий таймаут discovery ({discovery_timeout}s), "
                        f"обработано {len(apps)} приложений"
                    )

            logger.debug(f"Обнаружение завершено. Найдено приложений: {len(apps)}")

        except Exception as e:
            logger.error(f"Критическая ошибка в процессе обнаружения: {e}", exc_info=True)

        return apps