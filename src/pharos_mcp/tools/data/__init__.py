"""
SYSPRO domain knowledge data for Pharos MCP.

This package contains static data structures that encode SYSPRO-specific
knowledge about table naming conventions, module prefixes, lookup tables,
status codes, SQL templates, and help content.
"""

from .domain_map import SYSPRO_DOMAIN_MAP
from .modules import SYSPRO_MODULES, get_module_for_table
from .lookups import SYSPRO_LOOKUP_TABLES, SYSPRO_STATUS_CODES
from .templates import QUERY_TEMPLATES, TEMPLATE_DESCRIPTIONS
from .help_topics import HELP_TOPICS, TOPIC_ALIASES

__all__ = [
    "SYSPRO_DOMAIN_MAP",
    "SYSPRO_MODULES",
    "get_module_for_table",
    "SYSPRO_LOOKUP_TABLES",
    "SYSPRO_STATUS_CODES",
    "QUERY_TEMPLATES",
    "TEMPLATE_DESCRIPTIONS",
    "HELP_TOPICS",
    "TOPIC_ALIASES",
]
