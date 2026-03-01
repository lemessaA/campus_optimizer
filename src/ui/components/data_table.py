# src/ui/components/data_table.py
"""Data table template with optional chart."""
import streamlit as st
import pandas as pd
from typing import Optional, Dict, List, Any


def render_table(
    data: List[Dict[str, Any]],
    column_map: Optional[Dict[str, str]] = None,
    display_columns: Optional[List[str]] = None,
    max_rows: Optional[int] = None,
) -> Optional[pd.DataFrame]:
    """
    Render a styled data table.
    column_map: {api_key: display_name}
    display_columns: order of columns to show
    Returns DataFrame for optional chart use.
    """
    if not data:
        return None
    df = pd.DataFrame(data)
    if column_map:
        df = df.rename(columns=column_map)
    if display_columns:
        available = [c for c in display_columns if c in df.columns]
        df = df[available] if available else df
    if max_rows:
        df = df.head(max_rows)
    st.dataframe(df, use_container_width=True)
    return df


def table_with_chart(
    data: List[Dict[str, Any]],
    chart_type: str = "bar",
    x_col: Optional[str] = None,
    y_col: Optional[str] = None,
    color_col: Optional[str] = None,
    title: str = "",
    column_map: Optional[Dict[str, str]] = None,
) -> None:
    """Render table with optional Plotly chart below."""
    import plotly.express as px

    df = render_table(data, column_map=column_map)
    if df is None or df.empty:
        return
    if not x_col or not y_col:
        return
    x = column_map.get(x_col, x_col) if column_map else x_col
    y = column_map.get(y_col, y_col) if column_map else y_col
    if x not in df.columns or y not in df.columns:
        return
    color = None
    if color_col:
        color = column_map.get(color_col, color_col) if column_map else color_col
        if color not in df.columns:
            color = None
    if chart_type == "bar":
        fig = px.bar(df, x=x, y=y, color=color, title=title or f"{y} by {x}")
    elif chart_type == "line":
        fig = px.line(df, x=x, y=y, color=color, title=title or f"{y} over {x}")
    else:
        fig = px.bar(df, x=x, y=y, color=color, title=title)
    if "utilization" in y.lower() or "rate" in y.lower():
        fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)
