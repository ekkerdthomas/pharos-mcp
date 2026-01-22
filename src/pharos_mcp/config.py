"""
Configuration loading for Pharos MCP.

Loads YAML configuration files and environment variables.

Supports multiple configuration sources with the following priority:
1. Runtime registrations (via register_database tool) - highest priority
2. Client configs (via PHAROS_CLIENT_CONFIG or PHAROS_DATABASES env vars)
3. Server configs (from databases.yaml) - lowest priority
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for Pharos MCP.

    Supports hybrid configuration where:
    - Server defines default databases in databases.yaml (using env_prefix for credentials)
    - Clients can provide their own databases via:
      - PHAROS_CLIENT_CONFIG: Path to a YAML file with database definitions
      - PHAROS_DATABASES: JSON string with database definitions
    """

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
        self._client_databases: dict[str, Any] = {}

        self._load_configs()
        self._load_client_configs()

    def _load_configs(self) -> None:
        """Load all YAML configuration files."""
        self._databases = self._load_yaml("databases.yaml")
        self._tools = self._load_yaml("tools.yaml")
        self._prompts = self._load_yaml("prompts.yaml")

    def _load_client_configs(self) -> None:
        """Load client-provided database configurations.

        Checks for:
        - PHAROS_CLIENT_CONFIG: Path to a YAML file with database definitions
        - PHAROS_DATABASES: JSON string with database definitions

        Client configs have credentials inline (no env_prefix indirection).
        """
        # Load from YAML file if specified
        config_path = os.getenv("PHAROS_CLIENT_CONFIG")
        if config_path:
            path = Path(config_path)
            if path.exists():
                try:
                    with path.open() as f:
                        client_config = yaml.safe_load(f) or {}
                    databases = client_config.get("databases", {})
                    self._client_databases.update(databases)
                    logger.info(
                        f"Loaded {len(databases)} client database(s) from {config_path}"
                    )
                except Exception as e:
                    logger.error(f"Failed to load client config from {config_path}: {e}")
            else:
                logger.warning(f"PHAROS_CLIENT_CONFIG file not found: {config_path}")

        # Load from JSON env var if specified
        databases_json = os.getenv("PHAROS_DATABASES")
        if databases_json:
            try:
                databases = json.loads(databases_json)
                if isinstance(databases, dict):
                    self._client_databases.update(databases)
                    logger.info(
                        f"Loaded {len(databases)} client database(s) from PHAROS_DATABASES"
                    )
                else:
                    logger.error("PHAROS_DATABASES must be a JSON object")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PHAROS_DATABASES JSON: {e}")

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

        with filepath.open() as f:
            return yaml.safe_load(f) or {}

    @property
    def databases(self) -> dict[str, Any]:
        """Get server-configured database definitions (from databases.yaml)."""
        return self._databases.get("databases", {})

    @property
    def client_databases(self) -> dict[str, Any]:
        """Get client-configured database definitions.

        These come from PHAROS_CLIENT_CONFIG or PHAROS_DATABASES env vars.
        """
        return self._client_databases

    @property
    def all_databases(self) -> dict[str, Any]:
        """Get all database definitions (server and client merged).

        Client databases take precedence over server databases.
        """
        merged = dict(self.databases)
        merged.update(self._client_databases)
        return merged

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

        Checks client databases first, then server databases.
        Client databases have inline credentials; server databases use env_prefix.

        Args:
            name: Database name from config.

        Returns:
            Database configuration dictionary with connection details.

        Raises:
            ValueError: If database not found in config.
        """
        # Check client databases first (they have inline credentials)
        if name in self._client_databases:
            return self._get_client_database_config(name)

        # Fall back to server databases (use env_prefix for credentials)
        return self._get_server_database_config(name)

    def _get_client_database_config(self, name: str) -> dict[str, Any]:
        """Get configuration for a client-defined database.

        Client databases have credentials inline (no env_prefix).

        Args:
            name: Database name.

        Returns:
            Database configuration dictionary.
        """
        db_config = self._client_databases[name]
        db_type = db_config.get("type", "mssql").lower()

        # Client configs have credentials inline
        base_config = {
            "type": db_type,
            "database": db_config.get("database", ""),
            "user": db_config.get("user", db_config.get("username", "")),
            "password": db_config.get("password", ""),
            "readonly": db_config.get("readonly", True),
            "description": db_config.get("description", "Client-configured database"),
            "settings": {
                **self.global_settings,
                **db_config.get("settings", {}),
            },
        }

        # PostgreSQL uses host/port instead of server
        if db_type in ("postgresql", "postgres"):
            base_config["host"] = db_config.get("host", "")
            base_config["port"] = db_config.get("port", 5432)
        else:
            # SQL Server uses server
            base_config["server"] = db_config.get("server", "")
            base_config["trusted_connection"] = db_config.get(
                "trusted_connection", False
            )

        return base_config

    def _get_server_database_config(self, name: str) -> dict[str, Any]:
        """Get configuration for a server-defined database.

        Server databases use env_prefix to load credentials from environment.

        Args:
            name: Database name.

        Returns:
            Database configuration dictionary.

        Raises:
            ValueError: If database not found.
        """
        db_config = self.databases.get(name)
        if not db_config:
            raise ValueError(f"Database '{name}' not found in configuration")

        # Get credentials from environment
        env_prefix = db_config.get("env_prefix", "")
        db_type = db_config.get("type", "mssql").lower()

        # Base config common to all database types
        base_config = {
            "type": db_type,
            "database": os.getenv(f"{env_prefix}_NAME", ""),
            "user": os.getenv(f"{env_prefix}_USERNAME", ""),
            "password": os.getenv(f"{env_prefix}_PASSWORD", ""),
            "readonly": db_config.get("readonly", True),
            "description": db_config.get("description", ""),
            "settings": {
                **self.global_settings,
                **db_config.get("settings", {}),
            },
        }

        # PostgreSQL uses host/port instead of server
        if db_type in ("postgresql", "postgres"):
            base_config["host"] = os.getenv(f"{env_prefix}_HOST", "")
            base_config["port"] = int(os.getenv(f"{env_prefix}_PORT", "5432"))
        else:
            # SQL Server uses server
            base_config["server"] = os.getenv(f"{env_prefix}_SERVER", "")
            base_config["trusted_connection"] = os.getenv(
                f"{env_prefix}_TRUSTED_CONNECTION", "false"
            ).lower() == "true"

        return base_config

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
