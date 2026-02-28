"""Utility functions for OS detection and path handling."""
import os
import platform
import re
from pathlib import Path
from typing import Tuple


def detect_os() -> str:
    """Detect operating system.
    
    Returns:
        'windows', 'wsl', or 'linux'
    """
    system = platform.system().lower()
    
    if system == 'windows':
        return 'windows'
    elif system == 'linux':
        # Check if running in WSL
        try:
            with open('/proc/version', 'r') as f:
                if 'microsoft' in f.read().lower():
                    return 'wsl'
        except:
            pass
        return 'linux'
    else:
        return system


def is_windows_path(path: str) -> bool:
    """Check if path is Windows-style (e.g., C:\\path or C:/path).
    
    Args:
        path: Path string
        
    Returns:
        True if Windows path format
    """
    # Check for drive letter pattern
    return bool(re.match(r'^[A-Za-z]:[/\\]', path))


def is_wsl_path(path: str) -> bool:
    """Check if path is WSL-style (e.g., /mnt/c/path or /home/user/path).
    
    Args:
        path: Path string
        
    Returns:
        True if WSL/Linux path format
    """
    return path.startswith('/') and not path.startswith('//')


def normalize_path(path: str, target_os: str = None) -> str:
    """Normalize path for the target OS.
    
    Args:
        path: Path string
        target_os: Target OS ('windows', 'wsl', 'linux'), or None for current OS
        
    Returns:
        Normalized path
    """
    if target_os is None:
        target_os = detect_os()
    
    # Replace {workspace} placeholder if exists
    # (will be replaced later by actual workspace path)
    
    if target_os == 'windows':
        # Convert to Windows path
        if is_wsl_path(path):
            # Convert /mnt/c/... to C:/...
            match = re.match(r'^/mnt/([a-z])(/.*)?$', path)
            if match:
                drive = match.group(1).upper()
                rest = match.group(2) or ''
                path = f"{drive}:{rest}"
        # Ensure backslashes
        path = path.replace('/', '\\')
    else:
        # Convert to WSL/Linux path
        if is_windows_path(path):
            # Convert C:/... to /mnt/c/...
            match = re.match(r'^([A-Za-z]):(/.*)?$', path.replace('\\', '/'))
            if match:
                drive = match.group(1).lower()
                rest = match.group(2) or ''
                path = f"/mnt/{drive}{rest}"
        # Ensure forward slashes
        path = path.replace('\\', '/')
    
    return path


def get_shell_command(shell_type: str, command: str, cwd: str = None) -> Tuple[str, list]:
    """Get shell executable and command arguments for subprocess.
    
    Args:
        shell_type: 'bash', 'powershell', or 'cmd'
        command: Command string to execute
        cwd: Working directory (optional, should be in WSL/Linux format if using bash on Windows)
        
    Returns:
        Tuple of (executable, args_list)
    """
    current_os = detect_os()
    
    if shell_type == 'bash':
        if current_os == 'windows':
            # Use WSL bash on Windows
            executable = 'wsl'
            # If cwd is provided, prepend cd command
            if cwd:
                command = f"cd '{cwd}' && {command}"
            args = ['bash', '-lc', command]
        else:
            executable = 'bash'
            args = ['-lc', command]
    
    elif shell_type == 'powershell':
        if current_os == 'windows':
            executable = 'powershell.exe'
            args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command]
        else:
            # Try pwsh on Linux/WSL
            executable = 'pwsh'
            args = ['-NoProfile', '-Command', command]
    
    elif shell_type == 'cmd':
        if current_os == 'windows':
            executable = 'cmd.exe'
            args = ['/c', command]
        else:
            # Fallback to bash on Linux/WSL
            executable = 'bash'
            args = ['-c', command]
    
    else:
        # Default to bash
        executable = 'bash'
        args = ['-lc', command]
    
    return executable, args


def convert_wsl_network_path_to_linux(path: str) -> str:
    r"""Convert Windows WSL network path to Linux path.
    
    Converts paths like:
      \\wsl.localhost\Ubuntu\home\user\path
      \\wsl$\Ubuntu\home\user\path
    to:
      /home/user/path
    
    Args:
        path: Path string
        
    Returns:
        Converted path if WSL network path, otherwise original path
    """
    # Match \\wsl.localhost\<distro>\<path> or \\wsl$\<distro>\<path>
    patterns = [
        r'^\\\\wsl\.localhost\\[^\\]+\\(.*)$',
        r'^\\\\wsl\$\\[^\\]+\\(.*)$'
    ]
    
    for pattern in patterns:
        match = re.match(pattern, path, re.IGNORECASE)
        if match:
            linux_path = match.group(1)
            # Convert backslashes to forward slashes
            linux_path = linux_path.replace('\\', '/')
            # Ensure it starts with /
            if not linux_path.startswith('/'):
                linux_path = '/' + linux_path
            return linux_path
    
    return path


def resolve_workspace_path(path: str) -> str:
    """Resolve workspace path and check if it exists.
    
    Args:
        path: Workspace path
        
    Returns:
        Resolved absolute path
    """
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    
    # Try to resolve as Path object
    try:
        p = Path(path)
        if p.exists():
            return str(p.resolve())
    except:
        pass
    
    return path
