#!/usr/bin/env python3
"""
Тесты для фабрики create_process_manager.

Запуск: pytest tests/test_platforms/test_factory.py -v
"""
import pytest
import sys
from unittest.mock import MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.site_app.platforms import (
    create_process_manager,
    ProcessManagerInterface,
    SolarisProcessManager,
    SystemdProcessManager,
    PgrepProcessManager
)
from plugins.shell_executor import ShellExecutor


class TestFactory:
    """Тесты фабрики create_process_manager."""

    def test_create_solaris_manager(self):
        """Тест: создание SolarisProcessManager."""
        mock_shell = MagicMock(spec=ShellExecutor)

        manager = create_process_manager(
            platform='solaris',
            mode='systemd',  # Игнорируется для Solaris
            shell=mock_shell
        )

        assert isinstance(manager, SolarisProcessManager)
        assert isinstance(manager, ProcessManagerInterface)

    def test_create_systemd_manager(self):
        """Тест: создание SystemdProcessManager."""
        mock_shell = MagicMock(spec=ShellExecutor)

        manager = create_process_manager(
            platform='linux',
            mode='systemd',
            shell=mock_shell,
            systemd_pattern='{app_name}.service'
        )

        assert isinstance(manager, SystemdProcessManager)
        assert isinstance(manager, ProcessManagerInterface)

    def test_create_pgrep_manager(self):
        """Тест: создание PgrepProcessManager."""
        mock_shell = MagicMock(spec=ShellExecutor)

        manager = create_process_manager(
            platform='linux',
            mode='process',
            shell=mock_shell,
            pgrep_pattern='java.*{app_name}'
        )

        assert isinstance(manager, PgrepProcessManager)
        assert isinstance(manager, ProcessManagerInterface)

    def test_default_pgrep_for_unknown_mode(self):
        """Тест: неизвестный mode → PgrepProcessManager."""
        mock_shell = MagicMock(spec=ShellExecutor)

        manager = create_process_manager(
            platform='linux',
            mode='unknown',
            shell=mock_shell
        )

        assert isinstance(manager, PgrepProcessManager)

    def test_systemd_pattern_passed(self):
        """Тест: паттерн systemd передаётся в менеджер."""
        mock_shell = MagicMock(spec=ShellExecutor)

        manager = create_process_manager(
            platform='linux',
            mode='systemd',
            shell=mock_shell,
            systemd_pattern='app-{app_name}'
        )

        assert manager.service_pattern == 'app-{app_name}'

    def test_pgrep_pattern_passed(self):
        """Тест: паттерн pgrep передаётся в менеджер."""
        mock_shell = MagicMock(spec=ShellExecutor)

        manager = create_process_manager(
            platform='linux',
            mode='process',
            shell=mock_shell,
            pgrep_pattern='python.*{app_name}'
        )

        assert manager.pattern == 'python.*{app_name}'

    def test_default_patterns(self):
        """Тест: паттерны по умолчанию."""
        mock_shell = MagicMock(spec=ShellExecutor)

        # Systemd
        systemd_manager = create_process_manager(
            platform='linux',
            mode='systemd',
            shell=mock_shell
        )
        assert systemd_manager.service_pattern == '{app_name}'

        # Pgrep
        pgrep_manager = create_process_manager(
            platform='linux',
            mode='process',
            shell=mock_shell
        )
        assert pgrep_manager.pattern == 'java.*{app_name}'


class TestFactoryReturnsInterface:
    """Тесты что фабрика возвращает корректный интерфейс."""

    def test_all_managers_have_get_status(self):
        """Тест: все менеджеры имеют метод get_status."""
        mock_shell = MagicMock(spec=ShellExecutor)

        for platform, mode in [('solaris', 'systemd'), ('linux', 'systemd'), ('linux', 'process')]:
            manager = create_process_manager(platform, mode, mock_shell)
            assert callable(getattr(manager, 'get_status', None))

    def test_all_managers_have_get_pid(self):
        """Тест: все менеджеры имеют метод get_pid."""
        mock_shell = MagicMock(spec=ShellExecutor)

        for platform, mode in [('solaris', 'systemd'), ('linux', 'systemd'), ('linux', 'process')]:
            manager = create_process_manager(platform, mode, mock_shell)
            assert callable(getattr(manager, 'get_pid', None))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
