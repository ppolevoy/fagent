# plugins/site_app/platforms/solaris.py
"""
ProcessManager для Solaris через svcs.

Использует SMF (Service Management Facility) для получения статуса и PID.
"""
import logging
from typing import Tuple, Optional

from .base import ProcessManagerInterface
from ..shell_executor import ShellExecutor

logger = logging.getLogger(__name__)


class SolarisProcessManager(ProcessManagerInterface):
    """
    Менеджер процессов для Solaris через svcs.

    Использует svcs для получения статуса сервисов SMF.
    """

    def __init__(self, shell: ShellExecutor):
        """
        Args:
            shell: Экземпляр ShellExecutor
        """
        self.shell = shell

    def get_status(self, app_name: str) -> Tuple[str, str]:
        """
        Получить статус сервиса через svcs.
        """
        result = self.shell.run(["svcs", "-Ho", "state,stime", app_name])

        if result.success and result.stdout.strip():
            output = result.stdout.strip()
            parts = output.split(" ", 1)
            state = parts[0]
            start_time = parts[1].strip() if len(parts) > 1 else "Unknown"

            logger.debug(f"Статус {app_name}: {state}, запущен: {start_time}")
            return state, start_time
        else:
            logger.warning(f"Пустой ответ от svcs для {app_name}")

        return "unknown", "Unknown"

    def get_pid(self, app_name: str) -> Optional[int]:
        """
        Получить PID сервиса через svcs -p.
        """
        result = self.shell.run(["svcs", "-p", "-H", app_name])

        if result.success and result.stdout:
            lines = result.stdout.strip().split('\n')

            for line in lines:
                if not line or not line[0].isspace():
                    continue

                parts = line.strip().split()
                if len(parts) >= 2:
                    pid = None
                    process_name = 'unknown'

                    for i, part in enumerate(parts):
                        try:
                            pid = int(part)
                            process_name = parts[i + 1] if i + 1 < len(parts) else 'unknown'
                            break
                        except ValueError:
                            continue

                    if pid:
                        logger.debug(f"{app_name}: svcs найден PID {pid} ({process_name})")
                        return pid
                    else:
                        logger.debug(f"Не удалось найти PID в строке: {line.strip()}")
                        continue

            logger.debug(f"{app_name}: не найдено запущенных процессов")
        else:
            logger.debug(f"Пустой ответ от svcs -p для {app_name}")

        return None
