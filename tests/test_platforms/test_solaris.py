#!/usr/bin/env python3
"""
Тесты для SolarisProcessManager.

Запуск: pytest tests/test_platforms/test_solaris.py -v
"""
import pytest
import sys
from unittest.mock import MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.shell_executor import ShellResult
from plugins.site_app.platforms.solaris import SolarisProcessManager


class TestSolarisGetStatus:
    """Тесты получения статуса через svcs."""

    def test_get_status_online(self):
        """Тест: сервис online."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "online 10:30:00\n", "")

        manager = SolarisProcessManager(mock_shell)
        status, start_time = manager.get_status("myapp")

        assert status == "online"
        assert start_time == "10:30:00"
        mock_shell.run.assert_called_once_with(["svcs", "-Ho", "state,stime", "myapp"])

    def test_get_status_offline(self):
        """Тест: сервис offline."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "offline -\n", "")

        manager = SolarisProcessManager(mock_shell)
        status, start_time = manager.get_status("myapp")

        assert status == "offline"

    def test_get_status_maintenance(self):
        """Тест: сервис в maintenance."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "maintenance 9:00:00\n", "")

        manager = SolarisProcessManager(mock_shell)
        status, start_time = manager.get_status("myapp")

        assert status == "maintenance"
        assert start_time == "9:00:00"

    def test_get_status_empty_response(self):
        """Тест: пустой ответ от svcs."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "", "")

        manager = SolarisProcessManager(mock_shell)
        status, start_time = manager.get_status("myapp")

        assert status == "unknown"
        assert start_time == "Unknown"

    def test_get_status_service_not_found(self):
        """Тест: сервис не найден."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(1, "", "svcs: Pattern 'myapp' doesn't match any instances")

        manager = SolarisProcessManager(mock_shell)
        status, start_time = manager.get_status("myapp")

        assert status == "unknown"
        assert start_time == "Unknown"

    def test_get_status_only_state(self):
        """Тест: svcs возвращает только статус без времени."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "online\n", "")

        manager = SolarisProcessManager(mock_shell)
        status, start_time = manager.get_status("myapp")

        assert status == "online"
        assert start_time == "Unknown"


class TestSolarisGetPid:
    """Тесты получения PID через svcs -p."""

    def test_get_pid_found(self):
        """Тест: PID найден."""
        mock_shell = MagicMock()
        # svcs -p выводит строки с PID после строки статуса
        mock_shell.run.return_value = ShellResult(0, """svc:/application/myapp:default online
    12345 myapp
""", "")

        manager = SolarisProcessManager(mock_shell)
        pid = manager.get_pid("myapp")

        assert pid == 12345
        mock_shell.run.assert_called_once_with(["svcs", "-p", "-H", "myapp"])

    def test_get_pid_multiple_processes(self):
        """Тест: несколько процессов, берём первый."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, """svc:/application/myapp:default online
    12345 java
    12346 logger
""", "")

        manager = SolarisProcessManager(mock_shell)
        pid = manager.get_pid("myapp")

        assert pid == 12345

    def test_get_pid_not_running(self):
        """Тест: сервис не запущен."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "svc:/application/myapp:default offline\n", "")

        manager = SolarisProcessManager(mock_shell)
        pid = manager.get_pid("myapp")

        assert pid is None

    def test_get_pid_service_not_found(self):
        """Тест: сервис не найден."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(1, "", "svcs: Pattern 'myapp' doesn't match any instances")

        manager = SolarisProcessManager(mock_shell)
        pid = manager.get_pid("myapp")

        assert pid is None

    def test_get_pid_complex_output(self):
        """Тест: сложный формат вывода svcs -p."""
        mock_shell = MagicMock()
        # Реальный формат вывода svcs -p -H
        mock_shell.run.return_value = ShellResult(0, """online         Jan_15   svc:/application/myapp:default
                           99999 /usr/bin/java
""", "")

        manager = SolarisProcessManager(mock_shell)
        pid = manager.get_pid("myapp")

        assert pid == 99999


class TestSolarisInterface:
    """Тесты соответствия интерфейсу."""

    def test_implements_interface(self):
        """Тест: класс реализует ProcessManagerInterface."""
        from plugins.site_app.platforms.base import ProcessManagerInterface

        mock_shell = MagicMock()
        manager = SolarisProcessManager(mock_shell)

        assert isinstance(manager, ProcessManagerInterface)
        assert hasattr(manager, 'get_status')
        assert hasattr(manager, 'get_pid')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
