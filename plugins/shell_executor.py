# plugins/shell_executor.py
"""
ShellExecutor - обёртка над subprocess для централизованного выполнения команд.

Преимущества:
- Единая точка вызова subprocess
- Retry-логика при таймаутах
- Логирование всех вызовов
- Упрощённое тестирование через мок ShellExecutor
"""
import subprocess
import logging
import time
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ShellResult:
    """Результат выполнения shell-команды."""
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Команда выполнена успешно (returncode == 0)."""
        return self.returncode == 0


class ShellExecutor:
    """
    Обёртка над subprocess.run() с retry и логированием.

    Пример использования:
        executor = ShellExecutor(timeout=10, retries=2)
        result = executor.run(["pgrep", "-f", "java.*myapp"])
        if result.success:
            pid = int(result.stdout.strip())
    """

    def __init__(self, timeout: int = 10, retries: int = 1):
        """
        Args:
            timeout: Таймаут выполнения команды в секундах
            retries: Количество повторных попыток при таймауте
        """
        self.timeout = timeout
        self.retries = retries

    def run(self, cmd: List[str]) -> ShellResult:
        """
        Выполнить shell-команду.

        Args:
            cmd: Команда и аргументы в виде списка

        Returns:
            ShellResult: Результат выполнения
        """
        for attempt in range(self.retries):
            try:
                logger.debug(f"Выполняю: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )

                logger.debug(
                    f"Результат: returncode={result.returncode}, "
                    f"stdout={result.stdout[:100]}..." if len(result.stdout) > 100 else
                    f"Результат: returncode={result.returncode}, stdout={result.stdout.strip()}"
                )

                return ShellResult(
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr
                )

            except subprocess.TimeoutExpired:
                logger.warning(
                    f"Таймаут команды {cmd[0]} (попытка {attempt + 1}/{self.retries})"
                )
                if attempt == self.retries - 1:
                    return ShellResult(
                        returncode=-1,
                        stdout="",
                        stderr=f"Timeout after {self.timeout}s"
                    )
                # Пауза перед повторной попыткой
                time.sleep(1)

            except FileNotFoundError as e:
                logger.error(f"Команда не найдена: {cmd[0]}")
                return ShellResult(
                    returncode=-1,
                    stdout="",
                    stderr=f"Command not found: {cmd[0]}"
                )

            except Exception as e:
                logger.error(f"Ошибка выполнения {cmd[0]}: {e}")
                return ShellResult(
                    returncode=-1,
                    stdout="",
                    stderr=str(e)
                )

        # Не должны сюда попасть, но на всякий случай
        return ShellResult(returncode=-1, stdout="", stderr="Unknown error")
