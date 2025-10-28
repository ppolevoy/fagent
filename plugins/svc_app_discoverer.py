# plugins/svc_app_discoverer.py
import re
import subprocess
from pathlib import Path
from typing import List

from discovery import AbstractDiscoverer
from models import ApplicationInfo
from config import Config

class SVCAppDiscoverer(AbstractDiscoverer):
    """Плагин для обнаружения приложений, управляемых через svc (Solaris)."""

    def _get_app_status(self, app_name: str) -> tuple[str, str]:
        try:
            result = subprocess.run(
                ["svcs", "-Ho", "state,stime", app_name], 
                capture_output=True, 
                text=True
            )
            output = result.stdout.strip()
            if output:
                parts = output.split(" ", 1)
                state = parts[0]
                start_time = parts[1].strip() if len(parts) > 1 else "Unknown"
                return state, start_time
        except Exception:
            pass
        return "unknown", "unknown"

    def _get_app_version(self, app_name: str) -> str:
        htdoc_root = Config.SVC_HTPDOC_ROOT
        dir_symlink = htdoc_root / app_name
        jar_symlink = htdoc_root / f"{app_name}.jar"
        
        target_path = None
        if dir_symlink.is_symlink():
            target_path = dir_symlink.resolve()
        elif jar_symlink.is_symlink():
            target_path = jar_symlink.resolve()
        
        if not target_path:
            return "unknown-symlink"

        match = re.search(r"(?:\d{8}_\d{6}_[^\/+-|\/])?([\d\.]+)(?:\.jar)?$", str(target_path))
        return match.group(1) if match else "unknown-re"

    def discover(self) -> List[ApplicationInfo]:
        apps = []
        app_root = Config.SVC_APP_ROOT
        htdoc_root = Config.SVC_HTPDOC_ROOT

        if not (app_root.exists() and htdoc_root.exists()):
            return []

        app_names = {app_dir.name for app_dir in app_root.iterdir() if app_dir.is_dir()} 
        app_distrs = {htdoc.stem for htdoc in htdoc_root.iterdir() if htdoc.is_symlink()} 
        
        common_names = app_names & app_distrs
        
        for name in common_names:
            status, start_time = self._get_app_status(name)
            version = self._get_app_version(name)
            
            # Собираем метаданные, специфичные для этого типа приложений
            metadata = {
                "log_path": str((app_root / name / "logs").resolve()) if (app_root / name / "logs").is_symlink() else "Unknown",
                "distr_path": str((htdoc_root / name).resolve()) if (htdoc_root / name).is_symlink() else "Unknown",
            }
            
            apps.append(ApplicationInfo(
                name=name,
                version=version,
                status=status,
                start_time=start_time,
                metadata=metadata
            ))
            
        return apps