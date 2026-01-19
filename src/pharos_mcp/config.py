"""
Configuration loading for Pharos MCP.

Loads YAML configuration files and environment variables.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class Config:
    """Configuration manager for Pharos MCP."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize configuration from YAML files and environment.

        Args:
            config_dir: Path to config directory. Defaults to project config/.
        """
        # Load .env file
        load_dotenv()

        # Determine config directory
        if config_dir is None:
            # Default: look for config/ relative to project root
            # __file__ = src/pharos_mcp/config.py
            # .parent = src/pharos_mcp, .parent = src, .parent = project root
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config"

        self.config_dir = config_dir
        self._databases: dict[str, Any] = {}
        self._tools: dict[str, Any] = {}
        self._prompts: dict[str, Any] = {}

        self._load_configs()

    def _load_configs(self) -> None:
        """Load all YAML configuration files."""
        self._databases = self._load_yaml("databases.yaml")
        self._tools = self._load_yaml("tools.yaml")
        self._prompts = self._load_yaml("prompts.yaml")

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        """Load a YAML file from the config directory.

        Args:
            filename: Name of the YAML file to load.

        Returns:
            Parsed YAML content as a dictionary.
        """
        filepath = self.config_dir / filename
        if not filepath.exists():
            return {}

        with open(filepath) as f:
            return yaml.safe_load(f) or {}

    @property
    def databases(self) -> dict[str, Any]:
        """Get database configurations."""
        return self._databases.get("databases", {})

    @property
    def default_database(self) -> str:
        """Get the default database name."""
        return self._databases.get("default_database", "syspro_company")

    @property
    def global_settings(self) -> dict[str, Any]:
        """Get global database settings."""
        return self._databases.get("global_settings", {
            "query_timeout": 30,
            "max_rows": 1000,
            "connection_pool_size": 5,
        })

    @property
    def tools(self) -> dict[str, Any]:
        """Get tool configurations."""
        return self._tools.get("tools", {})

    @property
    def prompts(self) -> dict[str, Any]:
        """Get prompt templates."""
        return self._prompts.get("templates", {})

    def get_database_config(self, name: str) -> dict[str, Any]:
        """Get configuration for a specific database.

        Args:
            name: Database name from config.

        Returns:
            Database configuration dictionary with connection details.

        Raises:
            ValueError: If database not found in config.
        """
        db_config = self.databases.get(name)
        if not db_config:
            raise ValueError(f"Database '{name}' not found in configuration")

        # Get credentials from environment
        env_prefix = db_config.get("env_prefix", "")
        return {
            "server": os.getenv(f"{env_prefix}_SERVER", ""),
            "database": os.getenv(f"{env_prefix}_NAME", ""),
            "user": os.getenv(f"{env_prefix}_USERNAME", ""),
            "password": os.getenv(f"{env_prefix}_PASSWORD", ""),
            "trusted_connection": os.getenv(
                f"{env_prefix}_TRUSTED_CONNECTION", "false"
            ).lower() == "true",
            "readonly": db_config.get("readonly", True),
            "description": db_config.get("description", ""),
            "settings": {
                **self.global_settings,
                **db_config.get("settings", {}),
            },
        }

    def is_tool_enabled(self, category: str, tool_name: str) -> bool:
        """Check if a specific tool is enabled.

        Args:
            category: Tool category (schema, query, etc.)
            tool_name: Name of the tool.

        Returns:
            True if the tool is enabled.
        """
        category_config = self.tools.get(category, {})
        if not category_config.get("enabled", False):
            return False
        return tool_name in category_config.get("tools", [])


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        The Config singleton instance.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from files.

    Returns:
        Fresh Config instance.
    """
    global _config
    _config = Config()
    return _config
