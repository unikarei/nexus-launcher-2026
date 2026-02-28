"""Data models for launcher apps configuration."""
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class AppStatus(str, Enum):
    """Application status."""
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    ERROR = "Error"


class StartCommand(BaseModel):
    """Start command configuration."""
    cmd: str = Field(..., description="Command to execute")
    shell: str = Field(default="bash", description="Shell type: bash, powershell, cmd")
    cwd: Optional[str] = Field(default=None, description="Working directory (supports {workspace} placeholder)")


class HealthCheck(BaseModel):
    """Health check configuration."""
    url: str = Field(..., description="Health check URL")
    timeout_sec: int = Field(default=120, description="Timeout in seconds")


class OpenUrl(BaseModel):
    """URL to open in browser."""
    url: str = Field(..., description="URL to open")


class AppDefinition(BaseModel):
    """Application definition from apps.yaml."""
    id: str = Field(..., description="Unique application ID")
    name: str = Field(..., description="Display name")
    workspace: str = Field(..., description="Workspace path (repository folder)")
    start: List[StartCommand] = Field(..., description="Start commands")
    health: List[HealthCheck] = Field(..., description="Health check endpoints")
    open: List[OpenUrl] = Field(..., description="URLs to open")
    ports: List[int] = Field(default_factory=list, description="Ports used by the app")


class AppState(BaseModel):
    """Runtime state of an application."""
    id: str
    name: str
    workspace: str
    status: AppStatus = AppStatus.STOPPED
    message: Optional[str] = None
    last_check: Optional[str] = None
    ports: List[int] = Field(default_factory=list)
    open_urls: List[str] = Field(default_factory=list)
