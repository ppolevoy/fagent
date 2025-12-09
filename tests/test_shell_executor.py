#!/usr/bin/env python3
"""
Unit-тесты для ShellExecutor.

Запуск: pytest tests/test_shell_executor.py -v
"""
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.shell_executor import ShellExecutor, ShellResult


class TestShellResult:
    """Тесты для ShellResult."""

    def test_success_true(self):
        """Тест: success=True при returncode=0."""
        result = ShellResult(returncode=0, stdout="output", stderr="")
        assert result.success is True

    def test_success_false(self):
        """Тест: success=False при returncode!=0."""
        result = ShellResult(returncode=1, stdout="", stderr="error")
        assert result.success is False

    def test_success_false_negative(self):
        """Тест: success=False при отрицательном returncode."""
        result = ShellResult(returncode=-1, stdout="", stderr="timeout")
        assert result.success is False


class TestShellExecutorBasic:
    """Базовые тесты ShellExecutor."""

    def test_run_success(self):
        """Тест: успешное выполнение команды."""
        executor = ShellExecutor(timeout=5)
        result = executor.run(["echo", "hello"])

        assert result.success
        assert result.stdout.strip() == "hello"
        assert result.returncode == 0

    def test_run_failure(self):
        """Тест: неуспешная команда."""
        executor = ShellExecutor(timeout=5)
        result = executor.run(["false"])

        assert not result.success
        assert result.returncode != 0

    def test_run_command_not_found(self):
        """Тест: команда не найдена."""
        executor = ShellExecutor(timeout=5)
        result = executor.run(["nonexistent_command_xyz"])

        assert not result.success
        assert "not found" in result.stderr.lower()

    def test_run_with_args(self):
        """Тест: команда с аргументами."""
        executor = ShellExecutor(timeout=5)
        result = executor.run(["echo", "-n", "test"])

        assert result.success
        assert result.stdout == "test"


class TestShellExecutorTimeout:
    """Тесты таймаутов."""

    def test_run_timeout(self):
        """Тест: команда завершается по таймауту."""
        executor = ShellExecutor(timeout=1, retries=1)
        result = executor.run(["sleep", "10"])

        assert not result.success
        assert "Timeout" in result.stderr

    @patch('plugins.shell_executor.subprocess.run')
    def test_retry_on_timeout(self, mock_run):
        """Тест: retry при таймауте."""
        import subprocess

        # Первый вызов - таймаут, второй - успех
        mock_run.side_effect = [
            subprocess.TimeoutExpired(cmd=["test"], timeout=1),
            MagicMock(returncode=0, stdout="ok", stderr="")
        ]

        executor = ShellExecutor(timeout=1, retries=2)
        result = executor.run(["test"])

        assert result.success
        assert mock_run.call_count == 2

    @patch('plugins.shell_executor.subprocess.run')
    def test_all_retries_exhausted(self, mock_run):
        """Тест: все попытки исчерпаны."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["test"], timeout=1)

        executor = ShellExecutor(timeout=1, retries=3)
        result = executor.run(["test"])

        assert not result.success
        assert mock_run.call_count == 3


class TestShellExecutorConfig:
    """Тесты конфигурации."""

    def test_default_timeout(self):
        """Тест: таймаут по умолчанию."""
        executor = ShellExecutor()
        assert executor.timeout == 10

    def test_default_retries(self):
        """Тест: количество попыток по умолчанию."""
        executor = ShellExecutor()
        assert executor.retries == 1

    def test_custom_timeout(self):
        """Тест: пользовательский таймаут."""
        executor = ShellExecutor(timeout=30)
        assert executor.timeout == 30

    def test_custom_retries(self):
        """Тест: пользовательское количество попыток."""
        executor = ShellExecutor(retries=5)
        assert executor.retries == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
