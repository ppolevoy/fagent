#!/usr/bin/env python3
"""
Unit-тесты для DiscoveryScheduler.

Запуск: pytest tests/test_discovery_scheduler.py -v
"""
import pytest
import sys
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from discovery_scheduler import DiscoveryScheduler, DiscoveryCache
from models import ApplicationInfo


class TestDiscoveryCache:
    """Тесты для dataclass DiscoveryCache."""

    def test_cache_dataclass_fields(self):
        """Тест: DiscoveryCache имеет все необходимые поля."""
        cache = DiscoveryCache()

        assert hasattr(cache, 'apps')
        assert hasattr(cache, 'last_scan')
        assert hasattr(cache, 'scan_duration_ms')
        assert hasattr(cache, 'previous_state')
        assert hasattr(cache, 'error')

    def test_cache_default_values(self):
        """Тест: DiscoveryCache имеет правильные значения по умолчанию."""
        cache = DiscoveryCache()

        assert cache.apps == []
        assert cache.last_scan is None
        assert cache.scan_duration_ms == 0
        assert cache.previous_state == {}
        assert cache.error is None

    def test_cache_with_values(self):
        """Тест: DiscoveryCache можно создать с значениями."""
        now = datetime.now()
        apps = [ApplicationInfo(name="test", version="1.0", status="online")]

        cache = DiscoveryCache(
            apps=apps,
            last_scan=now,
            scan_duration_ms=100,
            previous_state={"test": "2025-01-01"},
            error="test error"
        )

        assert len(cache.apps) == 1
        assert cache.last_scan == now
        assert cache.scan_duration_ms == 100
        assert cache.previous_state == {"test": "2025-01-01"}
        assert cache.error == "test error"


class TestDiscoverySchedulerInit:
    """Тесты инициализации DiscoveryScheduler."""

    def test_init_creates_empty_cache(self):
        """Тест: __init__ создаёт пустой кэш."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)

        assert scheduler._cache.apps == []
        assert scheduler._cache.last_scan is None

    def test_init_does_not_start_thread(self):
        """Тест: __init__ НЕ запускает поток."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)

        assert scheduler._running is False
        assert scheduler._thread is None

    def test_init_stores_discovery_manager(self):
        """Тест: __init__ сохраняет discovery_manager."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)

        assert scheduler.discovery_manager is mock_dm

    def test_init_loads_config(self):
        """Тест: __init__ загружает конфигурацию."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)

        assert hasattr(scheduler, 'enabled')
        assert hasattr(scheduler, 'refresh_interval')
        assert hasattr(scheduler, 'stale_threshold')
        assert hasattr(scheduler, 'max_stale')
        assert hasattr(scheduler, 'jitter')


class TestDiscoverySchedulerStartStop:
    """Тесты start/stop DiscoveryScheduler."""

    def test_start_performs_initial_scan(self):
        """Тест: start() выполняет первичное сканирование."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            # Первичный скан должен был выполниться
            assert mock_dm.run_discovery.called
            assert len(scheduler.get_apps()) == 1
        finally:
            scheduler.stop()

    def test_start_starts_background_thread(self):
        """Тест: start() запускает фоновый поток."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            assert scheduler._running is True
            assert scheduler._thread is not None
            assert scheduler._thread.is_alive()
        finally:
            scheduler.stop()

    def test_stop_stops_thread(self):
        """Тест: stop() останавливает поток."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()
        scheduler.stop()

        assert scheduler._running is False
        assert not scheduler._thread.is_alive()

    def test_stop_is_idempotent(self):
        """Тест: stop() можно вызывать несколько раз."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()
        scheduler.stop()
        scheduler.stop()  # Повторный вызов не должен вызывать ошибку

        assert scheduler._running is False

    def test_start_when_disabled(self):
        """Тест: start() не запускает поток когда disabled."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.enabled = False
        scheduler.start()

        assert scheduler._running is False
        assert scheduler._thread is None

    def test_start_twice_no_error(self):
        """Тест: start() два раза не вызывает ошибку."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()
        scheduler.start()  # Повторный вызов

        try:
            assert scheduler._running is True
        finally:
            scheduler.stop()


class TestDiscoverySchedulerGetApps:
    """Тесты get_apps()."""

    def test_get_apps_returns_list(self):
        """Тест: get_apps() возвращает список."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            apps = scheduler.get_apps()
            assert isinstance(apps, list)
            assert len(apps) == 1
        finally:
            scheduler.stop()

    def test_get_apps_returns_copy_not_reference(self):
        """Тест: get_apps() возвращает копию, не ссылку."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            apps1 = scheduler.get_apps()
            apps2 = scheduler.get_apps()

            # Модификация одного списка не должна влиять на другой
            apps1.append(ApplicationInfo(name="app2", version="1.0", status="online"))
            assert len(apps1) == 2
            assert len(apps2) == 1  # apps2 не изменился
        finally:
            scheduler.stop()

    def test_get_apps_empty_before_start(self):
        """Тест: get_apps() возвращает пустой список до start()."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)
        apps = scheduler.get_apps()

        assert apps == []

    def test_get_apps_when_disabled_calls_discovery(self):
        """Тест: get_apps() при disabled вызывает discovery напрямую."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.enabled = False

        apps = scheduler.get_apps()

        # Должен был вызваться run_discovery напрямую
        assert mock_dm.run_discovery.called
        assert len(apps) == 1


class TestDiscoverySchedulerCacheInfo:
    """Тесты get_cache_info()."""

    def test_cache_info_has_required_fields(self):
        """Тест: get_cache_info() возвращает все необходимые поля."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            info = scheduler.get_cache_info()

            assert 'enabled' in info
            assert 'status' in info
            assert 'age_seconds' in info
            assert 'last_refresh' in info
            assert 'next_refresh_seconds' in info
            assert 'scan_duration_ms' in info
            assert 'error' in info
        finally:
            scheduler.stop()

    def test_cache_info_when_disabled(self):
        """Тест: get_cache_info() при disabled возвращает status=disabled."""
        mock_dm = MagicMock()

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.enabled = False

        info = scheduler.get_cache_info()

        assert info['enabled'] is False
        assert info['status'] == 'disabled'

    def test_cache_status_fresh(self):
        """Тест: status=fresh когда кэш свежий."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            info = scheduler.get_cache_info()
            # Только что сканировали - должен быть fresh
            assert info['status'] == 'fresh'
        finally:
            scheduler.stop()

    def test_cache_status_valid(self):
        """Тест: status=valid когда age > refresh_interval но < stale_threshold."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.refresh_interval = 10  # 10 сек
        scheduler.stale_threshold = 60  # 60 сек
        scheduler.start()

        try:
            # Искусственно состариваем кэш
            scheduler._cache.last_scan = datetime.now() - timedelta(seconds=15)

            info = scheduler.get_cache_info()
            assert info['status'] == 'valid'
        finally:
            scheduler.stop()

    def test_cache_status_stale(self):
        """Тест: status=stale когда age > stale_threshold но < max_stale."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.refresh_interval = 10
        scheduler.stale_threshold = 30
        scheduler.max_stale = 120
        scheduler.start()

        try:
            # Искусственно состариваем кэш
            scheduler._cache.last_scan = datetime.now() - timedelta(seconds=60)

            info = scheduler.get_cache_info()
            assert info['status'] == 'stale'
        finally:
            scheduler.stop()

    def test_cache_status_expired(self):
        """Тест: status=expired когда age > max_stale."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.refresh_interval = 10
        scheduler.stale_threshold = 30
        scheduler.max_stale = 60
        scheduler.start()

        try:
            # Искусственно состариваем кэш
            scheduler._cache.last_scan = datetime.now() - timedelta(seconds=120)

            info = scheduler.get_cache_info()
            assert info['status'] == 'expired'
        finally:
            scheduler.stop()


class TestDiscoverySchedulerForceRefresh:
    """Тесты force_refresh()."""

    def test_force_refresh_updates_cache(self):
        """Тест: force_refresh() обновляет кэш."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            # Изменяем возвращаемое значение
            mock_dm.run_discovery.return_value = [
                ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01"),
                ApplicationInfo(name="app2", version="2.0", status="online", start_time="2025-01-01")
            ]

            scheduler.force_refresh()

            apps = scheduler.get_apps()
            assert len(apps) == 2
        finally:
            scheduler.stop()

    def test_force_refresh_resets_age(self):
        """Тест: force_refresh() сбрасывает возраст кэша."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            # Искусственно состариваем кэш
            scheduler._cache.last_scan = datetime.now() - timedelta(seconds=100)

            old_info = scheduler.get_cache_info()
            assert old_info['age_seconds'] > 90

            scheduler.force_refresh()

            new_info = scheduler.get_cache_info()
            assert new_info['age_seconds'] < 1
        finally:
            scheduler.stop()


class TestDiscoverySchedulerChangeDetection:
    """Тесты детекции изменений."""

    def test_detect_changes_logs_restart(self):
        """Тест: _detect_changes логирует перезапуск приложения."""
        mock_dm = MagicMock()

        # Первое сканирование
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01 10:00:00")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            # Второе сканирование с изменённым start_time
            mock_dm.run_discovery.return_value = [
                ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01 11:00:00")
            ]

            with patch('discovery_scheduler.logger') as mock_logger:
                scheduler.force_refresh()

                # Должен был залогировать перезапуск
                log_calls = [str(c) for c in mock_logger.info.call_args_list]
                assert any("перезапуск" in c.lower() or "restarted" in c.lower() for c in log_calls)
        finally:
            scheduler.stop()

    def test_detect_new_app(self):
        """Тест: _detect_changes логирует новое приложение."""
        mock_dm = MagicMock()

        # Первое сканирование
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            # Добавляем новое приложение
            mock_dm.run_discovery.return_value = [
                ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01"),
                ApplicationInfo(name="app2", version="1.0", status="online", start_time="2025-01-01")
            ]

            with patch('discovery_scheduler.logger') as mock_logger:
                scheduler.force_refresh()

                # Должен был залогировать новое приложение
                log_calls = [str(c) for c in mock_logger.info.call_args_list]
                assert any("app2" in c for c in log_calls)
        finally:
            scheduler.stop()

    def test_detect_removed_app(self):
        """Тест: _detect_changes логирует удалённое приложение."""
        mock_dm = MagicMock()

        # Первое сканирование с двумя приложениями
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01"),
            ApplicationInfo(name="app2", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            # Удаляем одно приложение
            mock_dm.run_discovery.return_value = [
                ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
            ]

            with patch('discovery_scheduler.logger') as mock_logger:
                scheduler.force_refresh()

                # Должен был залогировать удаление
                log_calls = [str(c) for c in mock_logger.info.call_args_list]
                assert any("app2" in c for c in log_calls)
        finally:
            scheduler.stop()


class TestDiscoverySchedulerErrorHandling:
    """Тесты обработки ошибок."""

    def test_graceful_degradation_keeps_old_data(self):
        """Тест: при ошибке сканирования сохраняются старые данные."""
        mock_dm = MagicMock()

        # Первое успешное сканирование
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            assert len(scheduler.get_apps()) == 1

            # Следующее сканирование выбрасывает ошибку
            mock_dm.run_discovery.side_effect = Exception("Test error")

            # force_refresh должен выбросить ошибку, но данные сохранятся
            try:
                scheduler.force_refresh()
            except Exception:
                pass

            # Данные должны остаться
            assert len(scheduler.get_apps()) == 1
        finally:
            scheduler.stop()

    def test_error_stored_in_cache(self):
        """Тест: ошибка сохраняется в кэше."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = []

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            mock_dm.run_discovery.side_effect = Exception("Test error message")

            try:
                scheduler.force_refresh()
            except Exception:
                pass

            info = scheduler.get_cache_info()
            assert info['error'] is not None
            assert "Test error message" in info['error']
        finally:
            scheduler.stop()


class TestDiscoverySchedulerThreadSafety:
    """Тесты потокобезопасности."""

    def test_concurrent_get_apps_safe(self):
        """Тест: параллельные get_apps() безопасны."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            results = []
            errors = []

            def get_apps_thread():
                try:
                    for _ in range(100):
                        apps = scheduler.get_apps()
                        results.append(len(apps))
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=get_apps_thread) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            assert all(r == 1 for r in results)
        finally:
            scheduler.stop()

    def test_concurrent_refresh_safe(self):
        """Тест: параллельные force_refresh() безопасны."""
        mock_dm = MagicMock()
        mock_dm.run_discovery.return_value = [
            ApplicationInfo(name="app1", version="1.0", status="online", start_time="2025-01-01")
        ]

        scheduler = DiscoveryScheduler(mock_dm)
        scheduler.start()

        try:
            errors = []

            def refresh_thread():
                try:
                    for _ in range(10):
                        scheduler.force_refresh()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=refresh_thread) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
        finally:
            scheduler.stop()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
