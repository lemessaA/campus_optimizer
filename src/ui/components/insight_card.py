# src/ui/components/insight_card.py
"""Insight card template for analytics and recommendations."""
import streamlit as st
from typing import Dict, Any, List, Optional

# Type to icon/color mapping
INSIGHT_STYLES = {
    "optimization": ("💡", "info"),
    "warning": ("⚠️", "warning"),
    "info": ("ℹ️", "info"),
    "positive": ("✅", "success"),
    "error": ("❌", "error"),
}


def insight_card(insight: Dict[str, Any]) -> None:
    """Render a single insight card."""
    itype = insight.get("type", "info")
    icon, _ = INSIGHT_STYLES.get(itype, ("ℹ️", "info"))
    title = insight.get("title", "")
    detail = insight.get("detail", "")
    action = insight.get("action", "")

    st.markdown(f"**{icon} {title}**")
    st.caption(detail)
    if action:
        st.write(f"→ {action}")
    st.markdown("---")


def insight_list(insights: List[Dict[str, Any]]) -> None:
    """Render list of insight cards."""
    for insight in insights:
        insight_card(insight)


def recommendation_list(recommendations: List[str]) -> None:
    """Render list of recommendations as bullet points."""
    for rec in recommendations:
        st.markdown(f"- {rec}")
