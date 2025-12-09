# plugins/site_app/platforms/__init__.py
"""
$01@8:0 4;O A>740=8O ProcessManager 2 7028A8<>AB8 >B ?;0BD>@<K.
"""
from .base import ProcessManagerInterface
from .solaris import SolarisProcessManager
from .systemd import SystemdProcessManager
from .pgrep import PgrepProcessManager
from ..shell_executor import ShellExecutor


def create_process_manager(
    platform: str,
    mode: str,
    shell: ShellExecutor,
    systemd_pattern: str = "{app_name}",
    pgrep_pattern: str = "java.*{app_name}"
) -> ProcessManagerInterface:
    """
    $01@8:0 4;O A>740=8O ProcessManager.

    Args:
        platform: 'solaris' 8;8 'linux'
        mode:  568< 4;O Linux: 'systemd' 8;8 'process'
        shell: -:75<?;O@ ShellExecutor
        systemd_pattern: 0BB5@= 8<5=8 A5@28A0 systemd
        pgrep_pattern: 0BB5@= 4;O pgrep

    Returns:
        ProcessManagerInterface: >=:@5B=0O @50;870F8O 4;O ?;0BD>@<K
    """
    if platform == 'solaris':
        return SolarisProcessManager(shell)
    elif mode == 'systemd':
        return SystemdProcessManager(shell, systemd_pattern)
    else:
        return PgrepProcessManager(shell, pgrep_pattern)


__all__ = [
    'ProcessManagerInterface',
    'SolarisProcessManager',
    'SystemdProcessManager',
    'PgrepProcessManager',
    'create_process_manager'
]
