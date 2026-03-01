# src/ui/components/page_template.py
"""Page layout template: title, caption, optional breadcrumb."""
import streamlit as st
from typing import Optional, List


def page_header(
    title: str,
    caption: str = "",
    icon: str = "",
) -> None:
    """Render page header with title and caption."""
    display_title = f"{icon} {title}".strip() if icon else title
    st.title(display_title)
    if caption:
        st.caption(caption)


def page_with_sections(
    title: str,
    caption: str = "",
    icon: str = "",
    sections: Optional[List[tuple]] = None,
) -> None:
    """
    Render page with header and optional section dividers.
    sections: list of (section_title, section_content_callable)
    """
    page_header(title=title, caption=caption, icon=icon)
    if sections:
        for section_title, content_fn in sections:
            st.markdown("---")
            st.subheader(section_title)
            if callable(content_fn):
                content_fn()
            else:
                st.write(content_fn)


def breadcrumb(items: List[str]) -> None:
    """Render breadcrumb navigation."""
    path = " › ".join(items)
    st.caption(path)
