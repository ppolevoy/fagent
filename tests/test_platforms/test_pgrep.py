#!/usr/bin/env python3
"""
Тесты для PgrepProcessManager.

Запуск: pytest tests/test_platforms/test_pgrep.py -v
"""
import pytest
import sys
from unittest.mock import MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.shell_executor import ShellResult
from plugins.site_app.platforms.pgrep import PgrepProcessManager


class TestPgrepGetPid:
    """Тесты получения PID через pgrep."""

    def test_get_pid_found(self):
        """Тест: pgrep находит PID."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "12345\n", "")

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        pid = manager.get_pid("myapp")

        assert pid == 12345
        mock_shell.run.assert_called_once_with(["pgrep", "-f", "java.*myapp"])

    def test_get_pid_not_found(self):
        """Тест: процесс не найден."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(1, "", "")

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        pid = manager.get_pid("myapp")

        assert pid is None

    def test_get_pid_multiple_results(self):
        """Тест: pgrep возвращает несколько PID, берём первый."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "12345\n67890\n11111\n", "")

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        pid = manager.get_pid("myapp")

        assert pid == 12345

    def test_get_pid_empty_output(self):
        """Тест: пустой вывод pgrep."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "", "")

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        pid = manager.get_pid("myapp")

        assert pid is None

    def test_get_pid_custom_pattern(self):
        """Тест: кастомный паттерн для pgrep."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "99999\n", "")

        manager = PgrepProcessManager(mock_shell, "python.*{app_name}.py")
        pid = manager.get_pid("worker")

        assert pid == 99999
        mock_shell.run.assert_called_once_with(["pgrep", "-f", "python.*worker.py"])


class TestPgrepGetStatus:
    """Тесты получения статуса через pgrep."""

    def test_get_status_online(self):
        """Тест: процесс найден - статус online."""
        mock_shell = MagicMock()
        # pgrep возвращает PID
        mock_shell.run.side_effect = [
            ShellResult(0, "12345\n", ""),
            ShellResult(0, "Mon Dec  9 10:30:00 2025\n", "")
        ]

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "online"
        assert "Dec" in start_time

    def test_get_status_offline(self):
        """Тест: процесс не найден - статус offline."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(1, "", "")

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "offline"
        assert start_time == "Unknown"

    def test_get_status_start_time_unknown(self):
        """Тест: процесс найден, но ps не возвращает время."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "12345\n", ""),  # pgrep успешно
            ShellResult(1, "", "")  # ps неуспешно
        ]

        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "online"
        assert start_time == "Unknown"


class TestPgrepInterface:
    """Тесты соответствия интерфейсу."""

    def test_implements_interface(self):
        """Тест: класс реализует ProcessManagerInterface."""
        from plugins.site_app.platforms.base import ProcessManagerInterface

        mock_shell = MagicMock()
        manager = PgrepProcessManager(mock_shell, "java.*{app_name}")

        assert isinstance(manager, ProcessManagerInterface)
        assert hasattr(manager, 'get_status')
        assert hasattr(manager, 'get_pid')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
