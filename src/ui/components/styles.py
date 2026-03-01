# src/ui/components/styles.py
"""Global styles and theme for Campus Optimizer UI."""
import streamlit as st

# Color palette
COLORS = {
    "primary": "#58a6ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "muted": "#8b949e",
    "bg_dark": "#0e1117",
    "bg_card": "rgba(22, 27, 34, 0.8)",
    "border": "rgba(255, 255, 255, 0.08)",
}


def inject_global_styles() -> None:
    """Inject global CSS styles. Call once at app startup."""
    st.markdown(
        f"""
<style>
    /* Main app background */
    .stApp {{
        background: linear-gradient(160deg, {COLORS['bg_dark']} 0%, #1a1f2e 50%, {COLORS['bg_dark']} 100%);
    }}
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    }}
    [data-testid="stSidebar"] .stMarkdown {{ color: {COLORS['muted']}; }}
    /* Headers */
    h1, h2, h3 {{ color: #e6edf3 !important; }}
    /* Metric cards */
    [data-testid="stMetricValue"] {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {COLORS['primary']};
    }}
    [data-testid="stMetricLabel"] {{
        color: {COLORS['muted']};
        font-size: 0.85rem;
    }}
    /* DataFrames */
    .stDataFrame {{
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
    /* Expander */
    .streamlit-expanderHeader {{
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
    }}
    hr {{ border-color: {COLORS['border']}; margin: 1.5rem 0; }}
    /* Card template */
    .card-template {{
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }}
    /* Empty state */
    .empty-state {{
        text-align: center;
        padding: 2.5rem 1rem;
        color: {COLORS['muted']};
        border: 1px dashed {COLORS['border']};
        border-radius: 12px;
    }}
</style>
""",
        unsafe_allow_html=True,
    )
