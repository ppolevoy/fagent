# control_manager.py
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Dict, Optional

from control import AbstractController
from config import Config

logger = logging.getLogger(__name__)


class ControlManager:
    """
    Менеджер для загрузки и управления контроллерами.

    Автоматически загружает все контроллеры из директории controllers/
    """

    def __init__(self):
        """Инициализация менеджера контроллеров."""
        self.controllers: Dict[str, AbstractController] = {}
        self._load_controllers()

    def _load_controllers(self) -> None:
        """Динамически загружает все контроллеры из директории controllers/."""
        controllers_dir = Path(__file__).parent / "controllers"

        if not controllers_dir.exists():
            logger.warning(f"Директория контроллеров не существует: {controllers_dir}")
            return

        logger.info(f"Загрузка контроллеров из: {controllers_dir}")

        # Ищем все файлы *_controller.py
        for file_path in controllers_dir.glob("*_controller.py"):
            try:
                self._load_controller_from_file(file_path)
            except Exception as e:
                logger.error(f"Ошибка загрузки контроллера из {file_path}: {e}", exc_info=True)

        if not self.controllers:
            logger.warning("Не загружено ни одного контроллера")
        else:
            logger.info(f"Загружено контроллеров: {len(self.controllers)}")
            for name in self.controllers.keys():
                logger.info(f"  - {name}")

    def _load_controller_from_file(self, file_path: Path) -> None:
        """
        Загружает контроллер из файла.

        Args:
            file_path: Путь к файлу контроллера
        """
        module_name = file_path.stem
        logger.debug(f"Загрузка модуля: {module_name} из {file_path}")

        # Загружаем модуль
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            logger.warning(f"Не удалось создать спецификацию для {file_path}")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Ищем классы, наследующиеся от AbstractController
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and
                issubclass(obj, AbstractController) and
                obj is not AbstractController):

                try:
                    # Создаем экземпляр контроллера
                    controller_instance = obj()
                    controller_name = controller_instance.get_name()

                    # Проверяем на дубликаты
                    if controller_name in self.controllers:
                        logger.warning(
                            f"Контроллер с именем '{controller_name}' уже существует. "
                            f"Пропуск {name} из {file_path}"
                        )
                        continue

                    # Регистрируем контроллер
                    self.controllers[controller_name] = controller_instance
                    logger.info(f"  - Загружен контроллер: {controller_name} ({name})")

                except Exception as e:
                    logger.error(f"Ошибка инициализации контроллера {name}: {e}", exc_info=True)

    def get_controller(self, name: str) -> Optional[AbstractController]:
        """
        Получает контроллер по имени.

        Args:
            name: Имя контроллера

        Returns:
            Optional[AbstractController]: Контроллер или None если не найден
        """
        controller = self.controllers.get(name)
        if not controller:
            logger.warning(f"Контроллер '{name}' не найден")
        return controller

    def list_controllers(self) -> list[str]:
        """
        Возвращает список имен всех загруженных контроллеров.

        Returns:
            list[str]: Список имен контроллеров
        """
        return list(self.controllers.keys())

    def has_controller(self, name: str) -> bool:
        """
        Проверяет наличие контроллера.

        Args:
            name: Имя контроллера

        Returns:
            bool: True если контроллер существует
        """
        return name in self.controllers
