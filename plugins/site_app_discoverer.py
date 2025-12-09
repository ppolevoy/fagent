# plugins/site_app_discoverer.py
"""
Thin wrapper для обратной совместимости.

Реальная реализация находится в plugins/site_app/discoverer.py
"""
from plugins.site_app.discoverer import SiteAppDiscoverer

__all__ = ['SiteAppDiscoverer']
