# src/ui/components/tab_layout.py
"""Tab layout template for multi-section pages."""
import streamlit as st
from typing import List, Callable, Optional


def tab_page(
    tabs: List[tuple],
) -> None:
    """
    Render a page with tabs.
    tabs: list of (tab_label, content_callable)
    content_callable: function that renders the tab content (no args)
    """
    tab_labels = [t[0] for t in tabs]
    tab_objects = st.tabs(tab_labels)
    for tab_obj, (_, content_fn) in zip(tab_objects, tabs):
        with tab_obj:
            if callable(content_fn):
                content_fn()
            else:
                st.write(content_fn)
