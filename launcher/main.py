"""FastAPI main application for Local Web Launcher."""
import asyncio
import os
import socket
import sys
from contextlib import closing
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from pathlib import Path

from models import AppDefinition, AppState, StartCommand, HealthCheck, OpenUrl
from config import ConfigManager
from app_manager import AppManager


# Initialize FastAPI app
app = FastAPI(
    title="Nexus Web Launcher",
    description="Launch and manage local web applications",
    version="1.0.0"
)

# Setup paths
BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Initialize managers
config_manager = ConfigManager()
app_manager = AppManager()


# Frontend mode settings
LAUNCHER_ENV = os.environ.get("LAUNCHER_ENV", "development").strip().lower() or "development"
VITE_HOST = os.environ.get("VITE_HOST", "127.0.0.1").strip() or "127.0.0.1"
try:
    VITE_PORT = int((os.environ.get("VITE_PORT", "5173").strip() or "5173"))
except ValueError:
    VITE_PORT = 5173


def _is_vite_reachable(host: str = VITE_HOST, port: int = VITE_PORT, timeout_sec: float = 0.15) -> bool:
    """Return True when the Vite dev server is reachable."""
    try:
        with closing(socket.create_connection((host, int(port)), timeout=timeout_sec)):
            return True
    except Exception:
        return False


def _frontend_context() -> dict:
    """Build template context for frontend asset loading.

    Default behavior is development mode. In development mode, Vite is used
    when available; otherwise, static assets are served as a safe fallback.
    """
    env_mode = "development" if LAUNCHER_ENV not in {"production", "prod"} else "production"
    use_vite = env_mode == "development" and _is_vite_reachable()
    vite_origin = f"http://{VITE_HOST}:{VITE_PORT}"
    return {
        "launcher_env": env_mode,
        "use_vite": use_vite,
        "vite_origin": vite_origin,
    }


# API Models
class LaunchRequest(BaseModel):
    app_id: str


class AddAppRequest(BaseModel):
    id: str
    name: str
    workspace: str
    start_commands: List[dict]
    health_checks: List[dict]
    open_urls: List[str]
    ports: List[int]


class UpdateWorkspaceRequest(BaseModel):
    app_id: str
    workspace: str


# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main launcher page."""
    context = {"request": request, **_frontend_context()}
    return templates.TemplateResponse("index.html", context)


@app.get("/api/apps")
async def get_apps():
    """Get all applications and their states."""
    apps = config_manager.load_apps()
    
    # Refresh states
    await app_manager.refresh_states(apps)
    
    # Build response
    result = []
    for app in apps:
        state = app_manager.get_state(app.id)
        if not state:
            state = app_manager.init_state(app)
        
        result.append({
            "id": app.id,
            "name": app.name,
            "workspace": app.workspace,
            "status": state.status.value,
            "message": state.message,
            "last_check": state.last_check,
            "ports": app.ports,
            "open_urls": app_manager.resolve_open_urls(app)
        })
    
    return {"apps": result}


@app.post("/api/apps/launch")
async def launch_app(request: LaunchRequest):
    """Launch an application."""
    apps = config_manager.load_apps()
    app = next((a for a in apps if a.id == request.app_id), None)
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    result = await app_manager.launch_app(app)
    
    return result


@app.post("/api/apps/stop")
async def stop_app(request: LaunchRequest):
    """Stop an application."""
    success = await app_manager.stop_app(request.app_id)
    
    if success:
        return {"status": "success", "message": "Application stopped"}
    else:
        return {"status": "error", "message": "Failed to stop application"}


@app.get("/api/apps/{app_id}/logs")
async def get_logs(app_id: str, lines: int = 2000):
    """Get application logs."""
    log_content = app_manager.read_log(app_id, lines)
    
    return {"app_id": app_id, "logs": log_content}


@app.post("/api/apps/add")
async def add_app(request: AddAppRequest):
    """Add a new application."""
    try:
        # Convert request to AppDefinition
        start_commands = [
            StartCommand(
                cmd=cmd.get('cmd'),
                shell=cmd.get('shell', 'bash'),
                cwd=cmd.get('cwd')
            )
            for cmd in request.start_commands
        ]
        
        health_checks = [
            HealthCheck(
                url=health.get('url'),
                timeout_sec=health.get('timeout_sec', 120)
            )
            for health in request.health_checks
        ]
        
        open_urls = [OpenUrl(url=url) for url in request.open_urls]
        
        app = AppDefinition(
            id=request.id,
            name=request.name,
            workspace=request.workspace,
            start=start_commands,
            health=health_checks,
            open=open_urls,
            ports=request.ports
        )
        
        success = config_manager.add_app(app)
        
        if success:
            app_manager.init_state(app)
            return {"status": "success", "message": "Application added"}
        else:
            raise HTTPException(status_code=400, detail="Application ID already exists")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/apps/update-workspace")
async def update_workspace(request: UpdateWorkspaceRequest):
    """Update application workspace."""
    apps = config_manager.load_apps()
    app = next((a for a in apps if a.id == request.app_id), None)
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Update workspace
    app.workspace = request.workspace
    
    success = config_manager.update_app(app)
    
    if success:
        # Update state
        state = app_manager.get_state(app.id)
        if state:
            state.workspace = request.workspace
        
        return {"status": "success", "message": "Workspace updated"}
    else:
        raise HTTPException(status_code=400, detail="Failed to update workspace")


@app.delete("/api/apps/{app_id}")
async def delete_app(app_id: str):
    """Delete an application."""
    # Stop app first if running
    await app_manager.stop_app(app_id)
    
    # Delete from config
    success = config_manager.delete_app(app_id)
    
    if success:
        # Remove state
        if app_id in app_manager.app_states:
            del app_manager.app_states[app_id]
        
        return {"status": "success", "message": "Application deleted"}
    else:
        raise HTTPException(status_code=404, detail="Application not found")


@app.get("/api/health")
async def health_check():
    """Health check endpoint for launcher itself."""
    return {"status": "ok", "message": "Launcher is running"}


def main():
    """Run the launcher."""
    host = "127.0.0.1"

    env_port = os.environ.get("LAUNCHER_PORT", "").strip()
    port_was_explicit = bool(env_port)
    if env_port:
        try:
            preferred_port = int(env_port)
        except ValueError:
            print(f"[ERROR] Invalid LAUNCHER_PORT: {env_port!r}. Must be an integer.")
            sys.exit(2)
    else:
        preferred_port = 8080

    def is_port_available(check_host: str, check_port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((check_host, check_port))
            except OSError:
                return False
            return True

    def pick_port(check_host: str, start_port: int, max_tries: int = 20) -> int:
        if is_port_available(check_host, start_port):
            return start_port
        if port_was_explicit:
            print(
                f"[ERROR] Port {start_port} is already in use. "
                f"Either stop the process using it or choose another port with LAUNCHER_PORT.\n"
                f"        Example (PowerShell):  $env:LAUNCHER_PORT=8081; .\\01_start_launcher.bat\n"
                f"        Example (cmd):        set LAUNCHER_PORT=8081 & 01_start_launcher.bat\n"
                f"        Find PID:             netstat -ano | findstr :{start_port}\n"
                f"        Kill PID:             taskkill /PID <pid> /F"
            )
            sys.exit(1)
        for p in range(start_port + 1, start_port + 1 + max_tries):
            if is_port_available(check_host, p):
                print(f"[WARN] Port {start_port} is in use. Using {p} instead.")
                return p
        print(f"[ERROR] No free port found in range {start_port}-{start_port + max_tries}.")
        sys.exit(1)

    port = pick_port(host, preferred_port)

    print("=" * 60)
    print("  Nexus Web Launcher")
    print("=" * 60)
    print()
    print(f"  Starting launcher at http://{host}:{port}")
    print("  Press Ctrl+C to stop")
    print()
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
