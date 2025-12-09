# plugins/site_app/__init__.py
"""
0:5B site_app 4;O >1=0@C65=8O ?@8;>65=89 2 AB@C:BC@5 /site/app.

>445@68205B:
- Solaris: svcs (SMF)
- Linux: systemd 8;8 pgrep

A?>;L7>20=85:
    from plugins.site_app import SiteAppDiscoverer
"""
from .discoverer import SiteAppDiscoverer

__all__ = ['SiteAppDiscoverer']
