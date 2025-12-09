#!/usr/bin/env python3
"""
Unit-тесты для SiteAppDiscoverer.

Запуск: pytest tests/test_site_app_discoverer.py -v
"""
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins.site_app_discoverer import SiteAppDiscoverer
from plugins.site_app.shell_executor import ShellResult


class TestPlatformDetection:
    """Тесты определения платформы."""

    def test_detect_platform_linux(self):
        """Тест: определение Linux платформы."""
        with patch('sys.platform', 'linux'):
            discoverer = SiteAppDiscoverer()
            assert discoverer._detect_platform() == 'linux'

    def test_detect_platform_solaris(self):
        """Тест: определение Solaris платформы."""
        with patch('sys.platform', 'sunos5'):
            discoverer = SiteAppDiscoverer()
            assert discoverer._detect_platform() == 'solaris'


class TestRouting:
    """Тесты роутинга через Strategy pattern (process_manager_impl)."""

    def test_routing_delegates_to_process_manager(self):
        """Тест: _get_app_status делегирует на process_manager_impl."""
        discoverer = SiteAppDiscoverer()
        discoverer.process_manager_impl = MagicMock()
        discoverer.process_manager_impl.get_status.return_value = ("online", "10:30")

        status, start_time = discoverer._get_app_status("myapp")

        discoverer.process_manager_impl.get_status.assert_called_once_with("myapp")
        assert status == "online"
        assert start_time == "10:30"

    def test_routing_pid_delegates_to_process_manager(self):
        """Тест: _get_app_pid делегирует на process_manager_impl."""
        discoverer = SiteAppDiscoverer()
        discoverer.process_manager_impl = MagicMock()
        discoverer.process_manager_impl.get_pid.return_value = 12345

        pid = discoverer._get_app_pid("myapp")

        discoverer.process_manager_impl.get_pid.assert_called_once_with("myapp")
        assert pid == 12345

    def test_process_manager_impl_created_on_init(self):
        """Тест: process_manager_impl создаётся в __init__."""
        discoverer = SiteAppDiscoverer()

        assert hasattr(discoverer, 'process_manager_impl')
        assert discoverer.process_manager_impl is not None
        # Проверяем что это ProcessManagerInterface
        assert hasattr(discoverer.process_manager_impl, 'get_status')
        assert hasattr(discoverer.process_manager_impl, 'get_pid')


class TestListeningPorts:
    """Тесты получения портов."""

    def test_get_ports_linux_ss(self):
        """Тест: получение портов через ss на Linux."""
        discoverer = SiteAppDiscoverer()
        discoverer.platform = 'linux'

        # Мокаем shell.run с ShellResult
        discoverer.shell.run = MagicMock(return_value=ShellResult(
            returncode=0,
            stdout="""State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN  0       128     *:8080              *:*                users:(("java",pid=1234,fd=5))
LISTEN  0       128     *:22                *:*                users:(("sshd",pid=100,fd=3))
""",
            stderr=""
        ))

        ports = discoverer._get_listening_ports_netstat()

        assert 8080 in ports
        assert 22 in ports

    def test_get_ports_linux_ipv6(self):
        """Тест: получение портов с IPv6 адресами."""
        discoverer = SiteAppDiscoverer()
        discoverer.platform = 'linux'

        # Мокаем shell.run с ShellResult
        discoverer.shell.run = MagicMock(return_value=ShellResult(
            returncode=0,
            stdout="""State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN  0       128     [::]:8443           [::]:*             users:(("java",pid=1234,fd=5))
""",
            stderr=""
        ))

        ports = discoverer._get_listening_ports_netstat()

        assert 8443 in ports


class TestDiscoverEnabled:
    """Тесты флага enabled."""

    def test_discover_disabled(self):
        """Тест: discovery отключен."""
        discoverer = SiteAppDiscoverer()
        discoverer.enabled = False

        apps = discoverer.discover()

        assert apps == []


class TestPhase1Optimizations:
    """Тесты оптимизаций Фазы 1."""

    @patch.object(SiteAppDiscoverer, '_get_listening_ports_netstat')
    @patch.object(SiteAppDiscoverer, '_find_artifact')
    def test_ports_cached_once(self, mock_artifact, mock_ports):
        """Тест: порты кэшируются один раз за discover()."""
        mock_ports.return_value = {8080, 8081}
        mock_artifact.return_value = (None, None)  # Нет артефактов

        discoverer = SiteAppDiscoverer()
        discoverer.enabled = True
        discoverer.app_root = Path('/tmp/test_apps')
        discoverer.htdoc_root = Path('/tmp/test_htdoc')

        # Создаём временные директории
        discoverer.app_root.mkdir(parents=True, exist_ok=True)
        discoverer.htdoc_root.mkdir(parents=True, exist_ok=True)

        # Создаём тестовые директории приложений
        (discoverer.app_root / 'app1').mkdir(exist_ok=True)
        (discoverer.app_root / 'app2').mkdir(exist_ok=True)
        (discoverer.app_root / 'app3').mkdir(exist_ok=True)

        try:
            discoverer.discover()
            # _get_listening_ports_netstat должен вызываться только 1 раз
            assert mock_ports.call_count == 1
        finally:
            # Очистка
            import shutil
            shutil.rmtree('/tmp/test_apps', ignore_errors=True)
            shutil.rmtree('/tmp/test_htdoc', ignore_errors=True)

    @patch.object(SiteAppDiscoverer, '_parse_tomcat_server_xml')
    def test_port_no_heuristics(self, mock_xml):
        """Тест: без server.xml порт = None, а не угаданный."""
        mock_xml.return_value = None

        discoverer = SiteAppDiscoverer()
        discoverer._cached_ports = {8080, 8443, 9090}  # Порты есть, но не определяем по эвристике

        port = discoverer._get_app_port("unknown_app", 12345)

        # Без server.xml должен вернуть None, а не 8080 из common_ports
        assert port is None

    @patch.object(SiteAppDiscoverer, '_find_artifact')
    @patch.object(SiteAppDiscoverer, '_get_app_status')
    @patch.object(SiteAppDiscoverer, '_get_listening_ports_netstat')
    def test_early_artifact_filter(self, mock_ports, mock_status, mock_artifact):
        """Тест: приложение без артефакта не вызывает _get_app_status."""
        mock_ports.return_value = {}
        mock_artifact.return_value = (None, None)  # Нет артефакта

        discoverer = SiteAppDiscoverer()
        discoverer.enabled = True
        discoverer.app_root = Path('/tmp/test_apps_filter')
        discoverer.htdoc_root = Path('/tmp/test_htdoc_filter')

        # Создаём временные директории
        discoverer.app_root.mkdir(parents=True, exist_ok=True)
        discoverer.htdoc_root.mkdir(parents=True, exist_ok=True)
        (discoverer.app_root / 'noartifact_app').mkdir(exist_ok=True)

        try:
            discoverer.discover()

            # _find_artifact должен быть вызван
            mock_artifact.assert_called()
            # _get_app_status НЕ должен вызываться (ранняя фильтрация)
            mock_status.assert_not_called()
        finally:
            import shutil
            shutil.rmtree('/tmp/test_apps_filter', ignore_errors=True)
            shutil.rmtree('/tmp/test_htdoc_filter', ignore_errors=True)

    def test_subprocess_timeout_from_config(self):
        """Тест: таймаут subprocess берётся из конфига."""
        discoverer = SiteAppDiscoverer()

        # Проверяем что атрибут существует и имеет значение
        assert hasattr(discoverer, 'subprocess_timeout')
        assert discoverer.subprocess_timeout > 0

    def test_cached_ports_initialized(self):
        """Тест: _cached_ports инициализируется в __init__."""
        discoverer = SiteAppDiscoverer()

        assert hasattr(discoverer, '_cached_ports')
        assert discoverer._cached_ports is None  # До discover() должен быть None


class TestPhase4Parallel:
    """Тесты параллельного выполнения (Фаза 4)."""

    def test_discovery_workers_configured(self):
        """Тест: discovery_workers берётся из конфига."""
        discoverer = SiteAppDiscoverer()

        assert hasattr(discoverer, 'discovery_workers')
        assert discoverer.discovery_workers > 0
        assert isinstance(discoverer.discovery_workers, int)

    def test_process_single_app_method_exists(self):
        """Тест: метод _process_single_app существует."""
        discoverer = SiteAppDiscoverer()

        assert hasattr(discoverer, '_process_single_app')
        assert callable(discoverer._process_single_app)

    @patch.object(SiteAppDiscoverer, '_find_artifact')
    @patch.object(SiteAppDiscoverer, '_get_app_status')
    @patch.object(SiteAppDiscoverer, '_get_app_pid')
    @patch.object(SiteAppDiscoverer, '_get_app_port')
    @patch.object(SiteAppDiscoverer, '_extract_version')
    @patch.object(SiteAppDiscoverer, '_get_artifact_metadata')
    def test_process_single_app_returns_app_info(
        self, mock_metadata, mock_version, mock_port, mock_pid, mock_status, mock_artifact
    ):
        """Тест: _process_single_app возвращает ApplicationInfo."""
        mock_artifact.return_value = ('/path/to/app.war', 'war')
        mock_status.return_value = ('online', '2025-01-15 10:00:00')
        mock_pid.return_value = 12345
        mock_port.return_value = 8080
        mock_version.return_value = '1.0.0'
        mock_metadata.return_value = {'source': 'site-app'}

        discoverer = SiteAppDiscoverer()
        result = discoverer._process_single_app('myapp')

        assert result is not None
        assert result.name == 'myapp'
        assert result.version == '1.0.0'
        assert result.status == 'online'

    @patch.object(SiteAppDiscoverer, '_find_artifact')
    def test_process_single_app_no_artifact_returns_none(self, mock_artifact):
        """Тест: _process_single_app возвращает None если артефакт не найден."""
        mock_artifact.return_value = (None, None)

        discoverer = SiteAppDiscoverer()
        result = discoverer._process_single_app('noartifact_app')

        assert result is None

    @patch.object(SiteAppDiscoverer, '_find_artifact')
    def test_process_single_app_exception_returns_none(self, mock_artifact):
        """Тест: _process_single_app возвращает None при исключении."""
        mock_artifact.side_effect = Exception("Test exception")

        discoverer = SiteAppDiscoverer()
        result = discoverer._process_single_app('error_app')

        assert result is None

    @patch.object(SiteAppDiscoverer, '_process_single_app')
    @patch.object(SiteAppDiscoverer, '_get_listening_ports_netstat')
    def test_discover_uses_parallel_execution(self, mock_ports, mock_process):
        """Тест: discover использует параллельное выполнение."""
        mock_ports.return_value = {8080}
        # Возвращаем None для всех приложений (нет артефактов)
        mock_process.return_value = None

        discoverer = SiteAppDiscoverer()
        discoverer.enabled = True
        discoverer.app_root = Path('/tmp/test_parallel')
        discoverer.htdoc_root = Path('/tmp/test_parallel_htdoc')

        # Создаём временные директории
        discoverer.app_root.mkdir(parents=True, exist_ok=True)
        discoverer.htdoc_root.mkdir(parents=True, exist_ok=True)

        # Создаём тестовые приложения
        for i in range(5):
            (discoverer.app_root / f'app{i}').mkdir(exist_ok=True)

        try:
            discoverer.discover()

            # _process_single_app должен быть вызван для каждого приложения
            assert mock_process.call_count == 5
        finally:
            import shutil
            shutil.rmtree('/tmp/test_parallel', ignore_errors=True)
            shutil.rmtree('/tmp/test_parallel_htdoc', ignore_errors=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
