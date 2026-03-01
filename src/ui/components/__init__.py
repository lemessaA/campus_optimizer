# src/ui/components/__init__.py
"""Reusable UI component templates for Campus Optimizer."""
from .styles import inject_global_styles, COLORS
from .page_template import page_header, page_with_sections, breadcrumb
from .metric_card import metric_row, metric_grid
from .data_table import render_table, table_with_chart
from .form_card import form_card
from .empty_state import empty_state, loading_state
from .agent_status import agent_status_list, agent_health_cards
from .insight_card import insight_card, insight_list, recommendation_list
from .chart import bar_chart, line_chart, metric_chart
from .tab_layout import tab_page

__all__ = [
    "inject_global_styles",
    "COLORS",
    "page_header",
    "page_with_sections",
    "breadcrumb",
    "metric_row",
    "metric_grid",
    "render_table",
    "table_with_chart",
    "form_card",
    "empty_state",
    "loading_state",
    "agent_status_list",
    "agent_health_cards",
    "insight_card",
    "insight_list",
    "recommendation_list",
    "bar_chart",
    "line_chart",
    "metric_chart",
    "tab_page",
]
