# plugins/svc_app_discoverer.py
import re
import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from discovery import AbstractDiscoverer
from models import ApplicationInfo
from config import Config

logger = logging.getLogger(__name__)

class SVCAppDiscoverer(AbstractDiscoverer):
    """Плагин для обнаружения приложений, управляемых через svc (Solaris)."""

    ARTIFACT_CHECK_ORDER = ['war', 'jar', 'dir']

    def __init__(self):
        """Инициализация плагина с проверкой конфигурации"""
        super().__init__()
        self.app_root = Config.SVC_APP_ROOT
        self.htdoc_root = Config.SVC_HTPDOC_ROOT
        
        # Получаем список поддерживаемых расширений из конфигурации
        self.supported_extensions = getattr(
            Config, 
            'SUPPORTED_ARTIFACT_EXTENSIONS', 
            ['jar', 'war']
        )
        
        logger.info(
            f"SVCAppDiscoverer инициализирован. "
            f"Поддерживаемые расширения: {', '.join(self.supported_extensions)}"
        )
        
        # Проверяем доступность директорий
        self._validate_paths()
    
    def _validate_paths(self) -> None:
        """Проверка существования необходимых директорий"""
        if not self.app_root.exists():
            logger.warning(f"Директория приложений не существует: {self.app_root}")
        
        if not self.htdoc_root.exists():
            logger.warning(f"Директория дистрибутивов не существует: {self.htdoc_root}")
    
    def _get_app_status(self, app_name: str) -> Tuple[str, str]:
        """
        Получение статуса приложения через svcs.
        
        Args:
            app_name: Имя приложения (сервиса)
            
        Returns:
            Tuple[str, str]: (статус, время_запуска)
        """
        try:
            result = subprocess.run(
                ["svcs", "-Ho", "state,stime", app_name], 
                capture_output=True, 
                text=True,
                timeout=10  # Таймаут для предотвращения зависания
            )
            output = result.stdout.strip()
            if output:
                parts = output.split(" ", 1)
                state = parts[0]
                start_time = parts[1].strip() if len(parts) > 1 else "Unknown"
                
                logger.debug(f"Статус {app_name}: {state}, запущен: {start_time}")
                return state, start_time
            else:
                logger.warning(f"Пустой ответ от svcs для {app_name}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут при получении статуса {app_name}")
        except FileNotFoundError:
            logger.error("Команда svcs не найдена.")
        except Exception as e:
            logger.error(f"Ошибка при получении статуса {app_name}: {e}")
        
        return "unknown", "Unknown"
    
    def _find_artifact(self, app_name: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Поиск артефакта приложения (jar/war/dir).
        
        Args:
            app_name: Имя приложения
            
        Returns:
            Tuple[Optional[Path], Optional[str]]: (путь_к_артефакту, тип_артефакта)
        """
        # Проверяем артефакты в порядке приоритета
        for artifact_type in self.ARTIFACT_CHECK_ORDER:
            if artifact_type == 'dir':
                # Проверяем директорию (симлинк на директорию)
                dir_symlink = self.htdoc_root / app_name
                if dir_symlink.is_symlink() and dir_symlink.resolve().is_dir():
                    logger.debug(f"{app_name}: найдена директория {dir_symlink}")
                    return dir_symlink.resolve(), 'directory'
            else:
                # Проверяем файловые артефакты
                if artifact_type not in self.supported_extensions:
                    continue
                
                artifact_symlink = self.htdoc_root / f"{app_name}.{artifact_type}"
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
        
        logger.warning(f"{app_name}: артефакт не найден")
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
        artifact_type: Optional[str]
    ) -> Dict[str, Any]:
        """
        Сбор метаданных об артефакте.
        
        Args:
            app_name: Имя приложения
            artifact_path: Путь к артефакту
            artifact_type: Тип артефакта (jar/war/directory)
            
        Returns:
            Dict[str, Any]: Словарь с метаданными
        """
        metadata = {}
        
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
        
        return metadata

    def discover(self) -> List[ApplicationInfo]:
        """
        Основной метод обнаружения приложений.
        
        Returns:
            List[ApplicationInfo]: Список обнаруженных приложений
        """
        apps = []

        # Проверяем существование директорий
        if not (self.app_root.exists() and self.htdoc_root.exists()):
            logger.error(
                f"Требуемые директории не существуют. "
                f"app_root={self.app_root}, htdoc_root={self.htdoc_root}"
            )
            return []
        try:
            # Получаем список приложений и дистрибутивов
            app_names = {
                app_dir.name 
                for app_dir in self.app_root.iterdir() 
                if app_dir.is_dir()
            }
            
            app_distrs = {
                htdoc.stem 
                for htdoc in self.htdoc_root.iterdir() 
                if htdoc.is_symlink()
            }
            
            # Находим пересечение (приложения, у которых есть и директория, и дистрибутив)
            common_names = app_names & app_distrs
            
            logger.debug(
                f"Обнаружено приложений: {len(app_names)}, "
                f"дистрибутивов: {len(app_distrs)}, "
                f"совпадений: {len(common_names)}"
            )
            
            # Обрабатываем каждое приложение
            for name in sorted(common_names):
                try:
                    # Получаем статус через svcs
                    status, start_time = self._get_app_status(name)
                    
                    # Находим артефакт
                    artifact_path, artifact_type = self._find_artifact(name)
                    
                    # Извлекаем версию
                    version = self._extract_version(artifact_path)
                    
                    # Собираем метаданные
                    metadata = self._get_artifact_metadata(name, artifact_path, artifact_type)
                    
                    # Создаем объект приложения
                    app_info = ApplicationInfo(
                        name=name,
                        version=version,
                        status=status,
                        start_time=start_time,
                        metadata=metadata
                    )

                    apps.append(app_info)
                    logger.debug(f"Успешно обработано приложение: {name}")
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке приложения {name}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Обнаружение завершено. Найдено приложений: {len(apps)}")
            
        except Exception as e:
            logger.error(f"Критическая ошибка в процессе обнаружения: {e}", exc_info=True)
        
        return apps