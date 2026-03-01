# src/ui/components/metric_card.py
"""Metric card template for displaying KPIs."""
import streamlit as st
from typing import List, Tuple, Any


def metric_row(
    metrics: List[Tuple[str, Any]],
    columns: int = 4,
) -> None:
    """
    Render a row of metric cards.
    metrics: list of (label, value) tuples
    """
    cols = st.columns(columns)
    for i, (label, value) in enumerate(metrics):
        if i < len(cols):
            with cols[i]:
                st.metric(label, value)


def metric_grid(
    metrics: List[Tuple[str, Any]],
    cols_per_row: int = 4,
) -> None:
    """Render metrics in a responsive grid."""
    for i in range(0, len(metrics), cols_per_row):
        chunk = metrics[i : i + cols_per_row]
        metric_row(chunk, columns=len(chunk))
