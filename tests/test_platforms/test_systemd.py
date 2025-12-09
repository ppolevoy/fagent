#!/usr/bin/env python3
"""
Тесты для SystemdProcessManager.

Запуск: pytest tests/test_platforms/test_systemd.py -v
"""
import pytest
import sys
from unittest.mock import MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.shell_executor import ShellResult
from plugins.site_app.platforms.systemd import SystemdProcessManager


class TestSystemdGetStatus:
    """Тесты получения статуса через systemctl."""

    def test_get_status_active(self):
        """Тест: сервис активен."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "active\n", ""),
            ShellResult(0, "ActiveEnterTimestamp=Wed 2025-01-15 10:30:00 MSK\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "online"
        assert "2025-01-15" in start_time

    def test_get_status_inactive(self):
        """Тест: сервис неактивен."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "inactive\n", ""),
            ShellResult(0, "ActiveEnterTimestamp=\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "offline"

    def test_get_status_failed(self):
        """Тест: сервис в состоянии failed."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "failed\n", ""),
            ShellResult(0, "ActiveEnterTimestamp=\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "maintenance"

    def test_get_status_activating(self):
        """Тест: сервис запускается."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "activating\n", ""),
            ShellResult(0, "ActiveEnterTimestamp=\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "starting"

    def test_get_status_deactivating(self):
        """Тест: сервис останавливается."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "deactivating\n", ""),
            ShellResult(0, "ActiveEnterTimestamp=\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "stopping"

    def test_get_status_unknown(self):
        """Тест: неизвестный статус."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "reloading\n", ""),  # Неизвестный статус
            ShellResult(0, "ActiveEnterTimestamp=\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        status, start_time = manager.get_status("myapp")

        assert status == "unknown"

    def test_get_status_custom_pattern(self):
        """Тест: кастомный паттерн имени сервиса."""
        mock_shell = MagicMock()
        mock_shell.run.side_effect = [
            ShellResult(0, "active\n", ""),
            ShellResult(0, "ActiveEnterTimestamp=Thu 2025-01-16 12:00:00 UTC\n", "")
        ]

        manager = SystemdProcessManager(mock_shell, "app-{app_name}.service")
        status, start_time = manager.get_status("worker")

        # Проверяем что systemctl вызывается с правильным именем сервиса
        calls = mock_shell.run.call_args_list
        assert calls[0][0][0] == ["systemctl", "is-active", "app-worker.service"]


class TestSystemdGetPid:
    """Тесты получения PID через systemctl."""

    def test_get_pid_found(self):
        """Тест: PID найден."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "MainPID=12345\n", "")

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        pid = manager.get_pid("myapp")

        assert pid == 12345
        mock_shell.run.assert_called_once_with(
            ["systemctl", "show", "-p", "MainPID", "myapp"]
        )

    def test_get_pid_zero(self):
        """Тест: PID=0 (сервис не запущен)."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "MainPID=0\n", "")

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        pid = manager.get_pid("myapp")

        assert pid is None

    def test_get_pid_not_found(self):
        """Тест: сервис не существует."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(1, "", "Unit myapp.service could not be found.")

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        pid = manager.get_pid("myapp")

        assert pid is None

    def test_get_pid_invalid_output(self):
        """Тест: некорректный вывод systemctl."""
        mock_shell = MagicMock()
        mock_shell.run.return_value = ShellResult(0, "garbage\n", "")

        manager = SystemdProcessManager(mock_shell, "{app_name}")
        pid = manager.get_pid("myapp")

        assert pid is None


class TestSystemdInterface:
    """Тесты соответствия интерфейсу."""

    def test_implements_interface(self):
        """Тест: класс реализует ProcessManagerInterface."""
        from plugins.site_app.platforms.base import ProcessManagerInterface

        mock_shell = MagicMock()
        manager = SystemdProcessManager(mock_shell, "{app_name}")

        assert isinstance(manager, ProcessManagerInterface)
        assert hasattr(manager, 'get_status')
        assert hasattr(manager, 'get_pid')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
