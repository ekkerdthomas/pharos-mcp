"""
SYSPRO domain knowledge data for Pharos MCP.

This package contains static data structures that encode SYSPRO-specific
knowledge about table naming conventions, module prefixes, lookup tables,
status codes, SQL templates, and help content.
"""

from .domain_map import SYSPRO_DOMAIN_MAP
from .help_topics import HELP_TOPICS, TOPIC_ALIASES
from .lookups import SYSPRO_LOOKUP_TABLES, SYSPRO_STATUS_CODES
from .modules import SYSPRO_MODULES, get_module_for_table
from .templates import QUERY_TEMPLATES, TEMPLATE_DESCRIPTIONS

__all__ = [
    "HELP_TOPICS",
    "QUERY_TEMPLATES",
    "SYSPRO_DOMAIN_MAP",
    "SYSPRO_LOOKUP_TABLES",
    "SYSPRO_MODULES",
    "SYSPRO_STATUS_CODES",
    "TEMPLATE_DESCRIPTIONS",
    "TOPIC_ALIASES",
    "get_module_for_table",
]
