# src/ui/components/chart.py
"""Chart template wrapper for consistent Plotly charts."""
import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Optional, List


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
    y_format: Optional[str] = None,
) -> None:
    """Render bar chart with optional formatting."""
    if df.empty or x not in df.columns or y not in df.columns:
        return
    fig = px.bar(df, x=x, y=y, color=color, title=title or f"{y} by {x}")
    if y_format == "percent":
        fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: Optional[str] = None,
    title: str = "",
) -> None:
    """Render line chart."""
    if df.empty or x not in df.columns or y not in df.columns:
        return
    if color and color not in df.columns:
        color = None
    fig = px.line(df, x=x, y=y, color=color, title=title or f"{y} over {x}")
    st.plotly_chart(fig, use_container_width=True)


def metric_chart(
    data: List[dict],
    x_col: str,
    y_col: str,
    chart_type: str = "bar",
    title: str = "",
) -> None:
    """Render chart from list of dicts."""
    if not data:
        return
    df = pd.DataFrame(data)
    if chart_type == "line":
        line_chart(df, x_col, y_col, title=title)
    else:
        bar_chart(df, x_col, y_col, title=title)
