# plugins/site_app/platforms/systemd.py
"""
ProcessManager для Linux через systemd.

Использует systemctl для получения статуса и PID.
"""
import logging
from typing import Tuple, Optional

from .base import ProcessManagerInterface
from ..shell_executor import ShellExecutor

logger = logging.getLogger(__name__)


class SystemdProcessManager(ProcessManagerInterface):
    """
    Менеджер процессов для Linux через systemd.

    Использует systemctl для получения статуса сервисов.
    """

    def __init__(self, shell: ShellExecutor, service_pattern: str = "{app_name}"):
        """
        Args:
            shell: Экземпляр ShellExecutor
            service_pattern: Паттерн имени сервиса. Плейсхолдер {app_name} заменяется на имя приложения
        """
        self.shell = shell
        self.service_pattern = service_pattern

    def get_status(self, app_name: str) -> Tuple[str, str]:
        """
        Получить статус сервиса через systemctl.
        """
        service_name = self.service_pattern.format(app_name=app_name)

        # Получаем статус
        result = self.shell.run(["systemctl", "is-active", service_name])

        status_map = {
            'active': 'online',
            'inactive': 'offline',
            'failed': 'maintenance',
            'activating': 'starting',
            'deactivating': 'stopping'
        }
        raw_status = result.stdout.strip()
        status = status_map.get(raw_status, 'unknown')

        # Получаем время запуска
        result_time = self.shell.run(
            ["systemctl", "show", "-p", "ActiveEnterTimestamp", service_name]
        )
        start_time = "Unknown"
        if result_time.success:
            # ActiveEnterTimestamp=Wed 2025-01-15 10:30:00 MSK
            line = result_time.stdout.strip()
            if '=' in line:
                start_time = line.split('=', 1)[1].strip() or "Unknown"

        logger.debug(f"{app_name}: systemd статус={status}, запуск={start_time}")
        return status, start_time

    def get_pid(self, app_name: str) -> Optional[int]:
        """
        Получить PID сервиса через systemctl show.
        """
        service_name = self.service_pattern.format(app_name=app_name)

        result = self.shell.run(
            ["systemctl", "show", "-p", "MainPID", service_name]
        )

        if result.success:
            # MainPID=12345
            line = result.stdout.strip()
            if '=' in line:
                try:
                    pid_str = line.split('=')[1]
                    pid = int(pid_str)
                    if pid > 0:
                        logger.debug(f"{app_name}: systemd PID={pid}")
                        return pid
                except (ValueError, IndexError):
                    pass

        return None
