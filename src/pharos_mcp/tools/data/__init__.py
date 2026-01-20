"""
Domain knowledge data for Pharos MCP.

This package contains static data structures that encode domain-specific
knowledge about table naming conventions, module prefixes, lookup tables,
status codes, SQL templates, and help content for SYSPRO and Tempo systems.
"""

from .domain_map import SYSPRO_DOMAIN_MAP
from .help_topics import HELP_TOPICS, TOPIC_ALIASES
from .lookups import SYSPRO_LOOKUP_TABLES, SYSPRO_STATUS_CODES
from .modules import SYSPRO_MODULES, get_module_for_table
from .templates import QUERY_TEMPLATES, TEMPLATE_DESCRIPTIONS
from .tempo_domain_map import TEMPO_DOMAIN_MAP
from .tempo_modules import TEMPO_MODULES, get_tempo_module_for_table
from .tempo_templates import (
    TEMPO_QUERY_TEMPLATES,
    TEMPO_TEMPLATE_CATEGORIES,
    TEMPO_TEMPLATE_DESCRIPTIONS,
    get_tempo_template,
    get_tempo_template_description,
    list_tempo_templates,
)

__all__ = [
    "HELP_TOPICS",
    "QUERY_TEMPLATES",
    "SYSPRO_DOMAIN_MAP",
    "SYSPRO_LOOKUP_TABLES",
    "SYSPRO_MODULES",
    "SYSPRO_STATUS_CODES",
    "TEMPLATE_DESCRIPTIONS",
    "TEMPO_DOMAIN_MAP",
    "TEMPO_MODULES",
    "TEMPO_QUERY_TEMPLATES",
    "TEMPO_TEMPLATE_CATEGORIES",
    "TEMPO_TEMPLATE_DESCRIPTIONS",
    "TOPIC_ALIASES",
    "get_module_for_table",
    "get_tempo_module_for_table",
    "get_tempo_template",
    "get_tempo_template_description",
    "list_tempo_templates",
]
