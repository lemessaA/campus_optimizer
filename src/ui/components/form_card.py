# src/ui/components/form_card.py
"""Form card template: expandable form with consistent styling."""
import streamlit as st
from typing import Optional
from contextlib import contextmanager


@contextmanager
def form_card(
    title: str,
    expanded: bool = False,
    icon: str = "➕",
    key: Optional[str] = None,
):
    """
    Context manager for a form inside an expander.
    Add form fields and st.form_submit_button() inside the block.
    """
    display_title = f"{icon} {title}".strip() if icon else title
    form_key = key or display_title.replace(" ", "_").lower().replace("(", "").replace(")", "")
    with st.expander(display_title, expanded=expanded):
        with st.form(form_key):
            yield
