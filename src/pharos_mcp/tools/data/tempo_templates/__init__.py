"""
Tempo MRP query templates.

Modular templates organized by functional area:
- mrp_core: Demands, supply, suggestions, pegging
- forecasting: Forecast results, accuracy, methods
- inventory: Stock levels, ABC classification, buffers
- analytics: MRP runs, lead times, system metrics
"""

from .analytics import ANALYTICS_DESCRIPTIONS, ANALYTICS_TEMPLATES
from .forecasting import FORECASTING_DESCRIPTIONS, FORECASTING_TEMPLATES
from .inventory import INVENTORY_DESCRIPTIONS, INVENTORY_TEMPLATES
from .mrp_core import MRP_CORE_DESCRIPTIONS, MRP_CORE_TEMPLATES

# Combined templates dictionary
TEMPO_QUERY_TEMPLATES = {
    **MRP_CORE_TEMPLATES,
    **FORECASTING_TEMPLATES,
    **INVENTORY_TEMPLATES,
    **ANALYTICS_TEMPLATES,
}

# Combined descriptions dictionary
TEMPO_TEMPLATE_DESCRIPTIONS = {
    **MRP_CORE_DESCRIPTIONS,
    **FORECASTING_DESCRIPTIONS,
    **INVENTORY_DESCRIPTIONS,
    **ANALYTICS_DESCRIPTIONS,
}

# Template categories for organized listing
TEMPO_TEMPLATE_CATEGORIES = {
    "MRP Core": list(MRP_CORE_TEMPLATES.keys()),
    "Forecasting": list(FORECASTING_TEMPLATES.keys()),
    "Inventory & Classification": list(INVENTORY_TEMPLATES.keys()),
    "Analytics & System": list(ANALYTICS_TEMPLATES.keys()),
}


def get_tempo_template(template_name: str) -> str | None:
    """Get a Tempo query template by name."""
    return TEMPO_QUERY_TEMPLATES.get(template_name)


def get_tempo_template_description(template_name: str) -> str | None:
    """Get the description for a Tempo template."""
    return TEMPO_TEMPLATE_DESCRIPTIONS.get(template_name)


def list_tempo_templates() -> str:
    """Get a formatted list of all Tempo templates by category."""
    lines = ["Available Tempo MRP Query Templates:", "=" * 45]

    for category, templates in TEMPO_TEMPLATE_CATEGORIES.items():
        lines.append(f"\n{category}:")
        lines.append("-" * len(category))
        for name in templates:
            desc = TEMPO_TEMPLATE_DESCRIPTIONS.get(name, "")
            lines.append(f"  {name}: {desc}")

    return "\n".join(lines)


__all__ = [
    "TEMPO_QUERY_TEMPLATES",
    "TEMPO_TEMPLATE_DESCRIPTIONS",
    "TEMPO_TEMPLATE_CATEGORIES",
    "get_tempo_template",
    "get_tempo_template_description",
    "list_tempo_templates",
]
