"""Application lifecycle management."""
import asyncio
import subprocess
import time
import os
import re
import socket
from urllib.parse import urlparse, urlunparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import aiohttp
import psutil

from models import AppDefinition, AppState, AppStatus
from utils import get_shell_command, resolve_workspace_path, normalize_path, detect_os, convert_wsl_network_path_to_linux


class AppManager:
    """Manages application lifecycle (start, health check, state)."""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize app manager.
        
        Args:
            log_dir: Directory for application logs
        """
        self.log_dir = Path(log_dir)
        if not self.log_dir.is_absolute():
            launcher_dir = Path(__file__).parent
            self.log_dir = launcher_dir / self.log_dir
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Runtime state storage
        self.app_states: Dict[str, AppState] = {}
        
        # Process tracking
        self.processes: Dict[str, List[subprocess.Popen]] = {}

        # Cache for WSL distro IPs to avoid frequent wsl.exe calls
        # {distro: (ip, ts_epoch)}
        self._wsl_ip_cache: Dict[str, tuple[str, float]] = {}

    def _get_wsl_distro_from_workspace(self, workspace: str) -> Optional[str]:
        r"""Extract WSL distro name from a Windows UNC path like \\wsl.localhost\Ubuntu\..."""
        if not workspace:
            return None
        m = re.match(r'^\\\\wsl\.localhost\\([^\\]+)\\', workspace, flags=re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.match(r'^\\\\wsl\$\\([^\\]+)\\', workspace, flags=re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    def _get_wsl_ip(self, distro: str, *, cache_ttl_sec: float = 30.0) -> Optional[str]:
        """Return WSL distro IP address by calling `wsl.exe -d <distro> hostname -I`.

        Uses a short TTL cache because refresh runs frequently.
        """
        if not distro:
            return None
        now = time.time()
        cached = self._wsl_ip_cache.get(distro)
        if cached and (now - cached[1]) < cache_ttl_sec:
            return cached[0]

        try:
            cp = subprocess.run(
                ["wsl.exe", "-d", distro, "hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            out = (cp.stdout or "").strip()
            # `hostname -I` may return multiple addresses separated by spaces
            ip = out.split()[0] if out else None
            if ip:
                self._wsl_ip_cache[distro] = (ip, now)
            return ip
        except Exception:
            return None

    def _tcp_reachable(self, host: str, port: int, *, timeout_sec: float = 0.25) -> bool:
        # Try twice to avoid false negatives on busy machines.
        for _ in range(2):
            try:
                with socket.create_connection((host, int(port)), timeout=timeout_sec):
                    return True
            except Exception:
                continue
        return False

    def _windows_listener_process(self, port: int) -> Optional[str]:
        """Return the process name listening on the given TCP port on Windows.

        If multiple listeners exist, returns the first match. If not on Windows or
        not determinable, returns None.
        """
        try:
            if detect_os() != 'windows':
                return None
            for c in psutil.net_connections(kind='tcp'):
                if not c.laddr:
                    continue
                if int(getattr(c.laddr, 'port', -1)) != int(port):
                    continue
                if c.status != psutil.CONN_LISTEN:
                    continue
                if not c.pid:
                    continue
                try:
                    return psutil.Process(c.pid).name()
                except Exception:
                    return None
        except Exception:
            return None
        return None

    def _is_probably_wsl_proxy(self, proc_name: Optional[str]) -> bool:
        if not proc_name:
            return False
        n = proc_name.lower()
        # Observed names vary by Windows/WSL versions.
        return n in {
            'wslhost.exe',
            'wsl.exe',
            'wslservice.exe',
            'vmmem',
            'system',
        } or n.startswith('wsl')

    def resolve_open_urls(self, app: AppDefinition) -> List[str]:
        """Return URLs to open for the app.

        On Windows, when an app runs inside WSL, `http://localhost:<port>` can be
        shadowed by a Windows process already bound to the same port.
        If the workspace indicates a WSL distro UNC path, we try to rewrite
        loopback-host URLs to the WSL distro IP when that IP:port is reachable.
        """
        urls = [u.url for u in app.open]
        distro = self._get_wsl_distro_from_workspace(app.workspace)
        if not distro:
            return urls

        ip = self._get_wsl_ip(distro)
        if not ip:
            return urls

        resolved: List[str] = []
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    resolved.append(url)
                    continue

                hostname = parsed.hostname or ""
                port = parsed.port

                if hostname.lower() in ("127.0.0.1", "localhost") and port:
                    # Prefer WSL IP if reachable from Windows.
                    if self._tcp_reachable(ip, port, timeout_sec=1.0):
                        # Preserve scheme, port, path, query, fragment
                        netloc = f"{ip}:{port}"
                        if parsed.username or parsed.password:
                            # Unused in our config, but keep it correct
                            userinfo = parsed.username or ""
                            if parsed.password:
                                userinfo += f":{parsed.password}"
                            netloc = f"{userinfo}@{netloc}"
                        resolved.append(urlunparse(parsed._replace(netloc=netloc)))
                    else:
                        # If loopback port is owned by a non-WSL Windows process,
                        # opening it is very likely to show the wrong app.
                        listener = self._windows_listener_process(int(port))
                        if listener and not self._is_probably_wsl_proxy(listener):
                            self._write_log(
                                app.id,
                                f"WARN: Not opening {url} because {listener} is listening on localhost:{port} and WSL IP {ip}:{port} is not reachable."
                            )
                            continue
                        resolved.append(url)
                else:
                    resolved.append(url)
            except Exception:
                resolved.append(url)

        return resolved
    
    def get_state(self, app_id: str) -> Optional[AppState]:
        """Get current state of an application.
        
        Args:
            app_id: Application ID
            
        Returns:
            AppState or None
        """
        return self.app_states.get(app_id)
    
    def get_all_states(self) -> List[AppState]:
        """Get states of all applications.
        
        Returns:
            List of AppState objects
        """
        return list(self.app_states.values())
    
    def init_state(self, app: AppDefinition) -> AppState:
        """Initialize state for an application.
        
        Args:
            app: Application definition
            
        Returns:
            Initialized AppState
        """
        state = AppState(
            id=app.id,
            name=app.name,
            workspace=app.workspace,
            status=AppStatus.STOPPED,
            ports=app.ports,
            open_urls=[u.url for u in app.open]
        )
        self.app_states[app.id] = state
        return state
    
    async def check_health(self, app: AppDefinition, timeout: int = 5, *, emit_errors: bool = True) -> bool:
        """Check if application is healthy.
        
        Args:
            app: Application definition
            timeout: Request timeout in seconds
            
        Returns:
            True if healthy, False otherwise
        """
        async def port_reachable(port: int, connect_timeout_sec: float = 0.5) -> bool:
            """Return True if localhost port accepts TCP connections.

            Tries both IPv4 and IPv6 loopback to avoid platform-specific resolution issues.
            """

            async def try_host(host: str) -> bool:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host=host, port=port),
                        timeout=connect_timeout_sec,
                    )
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    return True
                except Exception:
                    return False

            # Succeed if either loopback family works.
            return await try_host("127.0.0.1") or await try_host("::1")

        has_http_checks = bool(getattr(app, "health", None))
        has_port_checks = bool(getattr(app, "ports", None))

        # If no health checks are configured, fall back to process liveness.
        # This supports CLI-style apps that don't expose an HTTP endpoint.
        if not has_http_checks and not has_port_checks:
            procs = self.processes.get(app.id, [])
            return any(p.poll() is None for p in procs)

        # Try each health check URL (HTTP)
        http_ok = False
        for health in app.health:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        health.url,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        if response.status < 500:  # 2xx, 3xx, 4xx are considered "up"
                            http_ok = True
                            break
            except Exception as e:
                # Log error but continue to next health check
                if emit_errors:
                    print(f"Health check failed for {app.id} at {health.url}: {e}")
                continue

        # If ports are declared, require them to be reachable too.
        ports_ok = True
        if getattr(app, "ports", None):
            for port in app.ports:
                if not await port_reachable(int(port)):
                    ports_ok = False
                    break

        # If only one kind of check was configured, don't require the other.
        if has_http_checks and has_port_checks:
            return http_ok and ports_ok
        if has_http_checks:
            return http_ok
        return ports_ok
    
    async def wait_for_health(self, app: AppDefinition, max_timeout: int = 120, *, emit_errors: bool = False) -> bool:
        """Wait for application to become healthy.
        
        Args:
            app: Application definition
            max_timeout: Maximum wait time in seconds
            
        Returns:
            True if became healthy, False if timeout
        """
        start_time = time.time()
        retry_interval = 2  # seconds
        
        while time.time() - start_time < max_timeout:
            if await self.check_health(app, timeout=5, emit_errors=emit_errors):
                return True
            
            await asyncio.sleep(retry_interval)
        
        return False
    
    def get_log_path(self, app_id: str) -> Path:
        """Get log file path for an application.
        
        Args:
            app_id: Application ID
            
        Returns:
            Path to log file
        """
        return self.log_dir / f"{app_id}.log"
    
    def read_log(self, app_id: str, lines: int = 2000) -> str:
        """Read log file for an application.
        
        Args:
            app_id: Application ID
            lines: Number of lines to read from end
            
        Returns:
            Log content
        """
        log_path = self.get_log_path(app_id)
        
        if not log_path.exists():
            return f"No log file found at {log_path}"
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading log: {e}"
    
    def _write_log(self, app_id: str, message: str):
        """Write message to application log.
        
        Args:
            app_id: Application ID
            message: Message to write
        """
        log_path = self.get_log_path(app_id)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"Error writing to log {log_path}: {e}")
    
    async def start_app(self, app: AppDefinition) -> bool:
        """Start an application.
        
        Args:
            app: Application definition
            
        Returns:
            True if start initiated successfully
        """
        state = self.app_states.get(app.id)
        if not state:
            state = self.init_state(app)
        
        # Update state to STARTING
        state.status = AppStatus.STARTING
        state.message = "Starting application..."
        state.last_check = datetime.now().isoformat()
        
        self._write_log(app.id, f"=== Starting {app.name} ===")
        
        # Check workspace exists
        workspace_path = resolve_workspace_path(app.workspace)
        if not Path(workspace_path).exists():
            error_msg = f"Workspace not found: {workspace_path}"
            state.status = AppStatus.ERROR
            state.message = error_msg
            self._write_log(app.id, f"ERROR: {error_msg}")
            return False
        
        # Execute start commands
        self.processes[app.id] = []
        
        for cmd in app.start:
            try:
                # Resolve working directory
                cwd = cmd.cwd or "{workspace}"
                cwd = cwd.replace("{workspace}", workspace_path)
                cwd = resolve_workspace_path(cwd)
                
                # If using bash shell and cwd is a WSL network path, convert it
                cwd_for_command = cwd
                if cmd.shell == 'bash' and detect_os() == 'windows':
                    cwd_for_command = convert_wsl_network_path_to_linux(cwd)

                # Replace {workspace} placeholder inside the command string too.
                command_str = cmd.cmd
                workspace_for_command = workspace_path
                if cmd.shell == 'bash' and detect_os() == 'windows':
                    workspace_for_command = convert_wsl_network_path_to_linux(workspace_path)
                command_str = command_str.replace("{workspace}", workspace_for_command)
                
                # Get shell command
                executable, args = get_shell_command(cmd.shell, command_str, cwd_for_command)
                
                # Build full command
                full_cmd = [executable] + args
                
                self._write_log(app.id, f"Executing: {' '.join(full_cmd)}")
                self._write_log(app.id, f"Working directory: {cwd} (command uses: {cwd_for_command})")
                
                # Open log file for output
                log_file = open(self.get_log_path(app.id), 'a', encoding='utf-8')
                
                # Start process
                # For bash on Windows, cwd is handled in the command itself, so pass None
                process_cwd = None if (cmd.shell == 'bash' and detect_os() == 'windows') else cwd
                process = subprocess.Popen(
                    full_cmd,
                    cwd=process_cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    shell=False
                )
                
                self.processes[app.id].append(process)
                self._write_log(app.id, f"Process started with PID: {process.pid}")

                # Fail fast if the process immediately exits (common for misconfigured scripts).
                await asyncio.sleep(0.2)
                rc = process.poll()
                if rc is not None:
                    error_msg = f"Process exited immediately with code {rc}"
                    state.status = AppStatus.ERROR
                    state.message = error_msg
                    self._write_log(app.id, f"ERROR: {error_msg}")
                    return False
                
            except Exception as e:
                error_msg = f"Failed to start command: {e}"
                state.status = AppStatus.ERROR
                state.message = error_msg
                self._write_log(app.id, f"ERROR: {error_msg}")
                return False
        
        # Start health check polling in background
        asyncio.create_task(self._poll_health(app))
        
        return True
    
    async def _poll_health(self, app: AppDefinition):
        """Poll health status until timeout.
        
        Args:
            app: Application definition
        """
        state = self.app_states[app.id]
        
        # Get max timeout from health checks
        max_timeout = max((h.timeout_sec for h in app.health), default=120)
        
        # Wait for health
        healthy = await self.wait_for_health(app, max_timeout, emit_errors=False)
        
        if healthy:
            state.status = AppStatus.RUNNING
            state.message = "Application is running"
            self._write_log(app.id, "Health check passed - application is running")
        else:
            state.status = AppStatus.ERROR
            state.message = f"Health check timeout after {max_timeout}s"
            self._write_log(app.id, f"ERROR: Health check timeout after {max_timeout}s")
        
        state.last_check = datetime.now().isoformat()
    
    async def launch_app(self, app: AppDefinition) -> Dict:
        """Launch application (check health, start if needed, open URLs).
        
        Args:
            app: Application definition
            
        Returns:
            Result dictionary with status and URLs
        """
        state = self.app_states.get(app.id)
        if not state:
            state = self.init_state(app)
        
        # Quick health check first
        if await self.check_health(app, timeout=3, emit_errors=False):
            # Already running
            state.status = AppStatus.RUNNING
            state.message = "Application is already running"
            state.last_check = datetime.now().isoformat()
            
            return {
                "status": "success",
                "message": "Application is already running",
                "open_urls": self.resolve_open_urls(app)
            }
        
        # Not running, start it
        success = await self.start_app(app)
        
        if not success:
            return {
                "status": "error",
                "message": state.message or "Failed to start application",
                "open_urls": []
            }
        
        # Wait for health (with progress updates)
        max_timeout = max((h.timeout_sec for h in app.health), default=120)
        healthy = await self.wait_for_health(app, max_timeout, emit_errors=False)
        
        if healthy:
            state.status = AppStatus.RUNNING
            state.message = "Application started successfully"
            state.last_check = datetime.now().isoformat()
            
            return {
                "status": "success",
                "message": "Application started successfully",
                "open_urls": self.resolve_open_urls(app)
            }
        else:
            state.status = AppStatus.ERROR
            state.message = f"Health check timeout after {max_timeout}s"
            state.last_check = datetime.now().isoformat()
            
            return {
                "status": "error",
                "message": state.message,
                "open_urls": []
            }
    
    async def stop_app(self, app_id: str) -> bool:
        """Stop an application.
        
        Args:
            app_id: Application ID
            
        Returns:
            True if stopped successfully
        """
        if app_id not in self.processes:
            return True
        
        processes = self.processes[app_id]
        
        for proc in processes:
            try:
                # Terminate process and children
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                
                for child in children:
                    child.terminate()
                parent.terminate()
                
                # Wait for termination
                gone, alive = psutil.wait_procs(children + [parent], timeout=5)
                
                # Force kill if still alive
                for p in alive:
                    p.kill()
                
            except Exception as e:
                print(f"Error stopping process: {e}")
        
        del self.processes[app_id]
        
        # Update state
        if app_id in self.app_states:
            self.app_states[app_id].status = AppStatus.STOPPED
            self.app_states[app_id].message = "Application stopped"
            self.app_states[app_id].last_check = datetime.now().isoformat()
        
        self._write_log(app_id, "Application stopped")
        
        return True
    
    async def refresh_states(self, apps: List[AppDefinition]):
        """Refresh states for all applications.
        
        Args:
            apps: List of application definitions
        """
        for app in apps:
            if app.id not in self.app_states:
                self.init_state(app)
            
            state = self.app_states[app.id]

            # Reap exited processes so we don't get stuck in STARTING forever.
            procs = self.processes.get(app.id, [])
            if procs:
                alive = [p for p in procs if p.poll() is None]
                if alive:
                    self.processes[app.id] = alive
                else:
                    # No alive processes left
                    self.processes.pop(app.id, None)
            
            has_http_checks = bool(getattr(app, "health", None))
            has_port_checks = bool(getattr(app, "ports", None))

            # Skip if currently starting AND we rely on external health/port checks.
            # For CLI-style apps (no checks configured), we still want to update
            # based on process liveness so the UI doesn't get stuck in STARTING.
            if state.status == AppStatus.STARTING and (has_http_checks or has_port_checks):
                continue
            
            # Check health
            healthy = await self.check_health(app, timeout=3, emit_errors=False)
            
            if healthy:
                state.status = AppStatus.RUNNING
                state.message = "Application is running"
            else:
                # Check if we have active processes
                if app.id in self.processes and self.processes[app.id]:
                    # Process exists but not healthy yet
                    state.status = AppStatus.STARTING
                    state.message = "Starting..."
                else:
                    state.status = AppStatus.STOPPED
                    state.message = "Application is stopped"
            
            state.last_check = datetime.now().isoformat()
