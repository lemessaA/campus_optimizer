# src/ui/components/empty_state.py
"""Empty state template when no data is available."""
import streamlit as st
from typing import Optional


def empty_state(
    message: str,
    icon: str = "📭",
    action_hint: Optional[str] = None,
) -> None:
    """Render empty state placeholder."""
    st.info(f"{icon} {message}")
    if action_hint:
        st.caption(action_hint)


def loading_state(message: str = "Loading…") -> None:
    """Render loading spinner."""
    st.spinner(message)
