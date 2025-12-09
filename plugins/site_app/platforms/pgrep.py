# plugins/site_app/platforms/pgrep.py
"""
ProcessManager для Linux через pgrep.

Определяет статус по наличию процесса.
"""
import logging
from typing import Tuple, Optional

from .base import ProcessManagerInterface
from ..shell_executor import ShellExecutor

logger = logging.getLogger(__name__)


class PgrepProcessManager(ProcessManagerInterface):
    """
    Менеджер процессов для Linux через pgrep.

    Использует pgrep -f для поиска процессов по паттерну.
    """

    def __init__(self, shell: ShellExecutor, pattern: str = "java.*{app_name}"):
        """
        Args:
            shell: Экземпляр ShellExecutor
            pattern: Паттерн для pgrep. Плейсхолдер {app_name} заменяется на имя приложения
        """
        self.shell = shell
        self.pattern = pattern

    def get_pid(self, app_name: str) -> Optional[int]:
        """
        Получить PID через pgrep -f.
        """
        pattern = self.pattern.format(app_name=app_name)
        result = self.shell.run(["pgrep", "-f", pattern])

        if result.success and result.stdout.strip():
            try:
                # pgrep может вернуть несколько PID, берём первый
                pids = result.stdout.strip().split('\n')
                pid = int(pids[0])
                logger.debug(f"{app_name}: pgrep найден PID={pid}")
                return pid
            except (ValueError, IndexError):
                pass

        return None

    def get_status(self, app_name: str) -> Tuple[str, str]:
        """
        Определить статус по наличию процесса.
        """
        pid = self.get_pid(app_name)

        if pid is None:
            return "offline", "Unknown"

        # Процесс найден - получаем время запуска через ps
        start_time = self._get_process_start_time(pid)

        logger.debug(f"{app_name}: process статус=online, PID={pid}, запуск={start_time}")
        return "online", start_time

    def _get_process_start_time(self, pid: int) -> str:
        """
        Получить время запуска процесса через ps.
        """
        result = self.shell.run(["ps", "-o", "lstart=", "-p", str(pid)])

        if result.success and result.stdout.strip():
            return result.stdout.strip()

        return "Unknown"
