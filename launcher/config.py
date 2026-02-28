"""Configuration file management."""
import os
import yaml
from typing import List, Dict, Any
from pathlib import Path
from models import AppDefinition, StartCommand, HealthCheck, OpenUrl


class ConfigManager:
    """Manages apps.yaml configuration file."""
    
    def __init__(self, config_path: str = "apps.yaml"):
        """Initialize config manager.
        
        Args:
            config_path: Path to apps.yaml file
        """
        self.config_path = Path(config_path)
        if not self.config_path.is_absolute():
            # Make path relative to launcher directory
            launcher_dir = Path(__file__).parent
            self.config_path = launcher_dir / self.config_path
    
    def load_apps(self) -> List[AppDefinition]:
        """Load application definitions from apps.yaml.
        
        Returns:
            List of AppDefinition objects
        """
        print(f"[DEBUG] Loading apps from: {self.config_path}")
        print(f"[DEBUG] Config file exists: {self.config_path.exists()}")
        
        if not self.config_path.exists():
            # Return empty list if config doesn't exist yet
            print(f"[WARNING] Config file not found at {self.config_path}")
            return []
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            print(f"[DEBUG] Loaded YAML data: {data}")
            
            if not data:
                print("[WARNING] YAML file is empty")
                return []
            
            apps = []
            for app_data in data:
                # Parse start commands
                start_commands = []
                for cmd_data in app_data.get('start', []):
                    if isinstance(cmd_data, str):
                        # Simple string format
                        start_commands.append(StartCommand(cmd=cmd_data))
                    else:
                        start_commands.append(StartCommand(**cmd_data))
                
                # Parse health checks
                health_checks = []
                for health_data in app_data.get('health', []):
                    if isinstance(health_data, str):
                        health_checks.append(HealthCheck(url=health_data))
                    else:
                        health_checks.append(HealthCheck(**health_data))
                
                # Parse open URLs
                open_urls = []
                for url_data in app_data.get('open', []):
                    if isinstance(url_data, str):
                        open_urls.append(OpenUrl(url=url_data))
                    else:
                        open_urls.append(OpenUrl(**url_data))
                
                app = AppDefinition(
                    id=app_data['id'],
                    name=app_data['name'],
                    workspace=app_data['workspace'],
                    start=start_commands,
                    health=health_checks,
                    open=open_urls,
                    ports=app_data.get('ports', [])
                )
                apps.append(app)
                print(f"[DEBUG] Loaded app: {app.id} - {app.name}")
            
            print(f"[DEBUG] Total apps loaded: {len(apps)}")
            return apps
        
        except Exception as e:
            print(f"[ERROR] Error loading apps.yaml: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def save_apps(self, apps: List[AppDefinition]) -> bool:
        """Save application definitions to apps.yaml.
        
        Args:
            apps: List of AppDefinition objects
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert to dict format
            data = []
            for app in apps:
                app_dict = {
                    'id': app.id,
                    'name': app.name,
                    'workspace': app.workspace,
                    'start': [
                        {
                            'cmd': cmd.cmd,
                            'shell': cmd.shell,
                            'cwd': cmd.cwd
                        } if cmd.cwd else {
                            'cmd': cmd.cmd,
                            'shell': cmd.shell
                        }
                        for cmd in app.start
                    ],
                    'health': [
                        {'url': h.url, 'timeout_sec': h.timeout_sec}
                        for h in app.health
                    ],
                    'open': [
                        {'url': u.url}
                        for u in app.open
                    ],
                    'ports': app.ports
                }
                data.append(app_dict)
            
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write YAML
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            return True
        
        except Exception as e:
            print(f"Error saving apps.yaml: {e}")
            return False
    
    def add_app(self, app: AppDefinition) -> bool:
        """Add a new application to configuration.
        
        Args:
            app: AppDefinition to add
            
        Returns:
            True if successful, False otherwise
        """
        apps = self.load_apps()
        
        # Check if app ID already exists
        if any(a.id == app.id for a in apps):
            return False
        
        apps.append(app)
        return self.save_apps(apps)
    
    def update_app(self, app: AppDefinition) -> bool:
        """Update an existing application in configuration.
        
        Args:
            app: AppDefinition to update
            
        Returns:
            True if successful, False otherwise
        """
        apps = self.load_apps()
        
        # Find and replace
        for i, a in enumerate(apps):
            if a.id == app.id:
                apps[i] = app
                return self.save_apps(apps)
        
        return False
    
    def delete_app(self, app_id: str) -> bool:
        """Delete an application from configuration.
        
        Args:
            app_id: Application ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        apps = self.load_apps()
        apps = [a for a in apps if a.id != app_id]
        return self.save_apps(apps)
