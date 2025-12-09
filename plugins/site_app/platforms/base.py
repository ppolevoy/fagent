# plugins/site_app/platforms/base.py
"""
Базовый интерфейс для менеджеров процессов.

Паттерн Strategy: каждая платформа (Solaris, Linux systemd, Linux pgrep)
реализует этот интерфейс для получения статуса и PID приложений.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional


class ProcessManagerInterface(ABC):
    """
    Абстрактный интерфейс для управления процессами.

    Реализации:
    - SolarisProcessManager: использует svcs
    - SystemdProcessManager: использует systemctl
    - PgrepProcessManager: использует pgrep
    """

    @abstractmethod
    def get_status(self, app_name: str) -> Tuple[str, str]:
        """
        Получить статус приложения.

        Args:
            app_name: Имя приложения

        Returns:
            Tuple[str, str]: (статус, время_запуска)
                статус: 'online', 'offline', 'maintenance', 'unknown'
                время_запуска: строка с временем или 'Unknown'
        """
        pass

    @abstractmethod
    def get_pid(self, app_name: str) -> Optional[int]:
        """
        Получить PID процесса приложения.

        Args:
            app_name: Имя приложения

        Returns:
            Optional[int]: PID процесса или None если не найден
        """
        pass
