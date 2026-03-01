# src/ui/components/agent_status.py
"""Agent status display template."""
import streamlit as st
from typing import Dict, Any, Optional


def agent_status_list(agents: Dict[str, str]) -> None:
    """Render list of agent statuses with status indicator."""
    if not agents:
        return
    for name, status in agents.items():
        display_name = name.replace("_", " ").title()
        if status == "active":
            st.markdown(f"- **{display_name}**: 🟢 Active")
        else:
            st.markdown(f"- **{display_name}**: 🟡 {str(status)}")


def agent_health_cards(agents: Dict[str, Any]) -> None:
    """Render agent health metrics as cards."""
    if not agents:
        return
    cols = st.columns(min(len(agents), 4))
    for i, (name, info) in enumerate(agents.items()):
        if isinstance(info, dict):
            status = info.get("status", "unknown")
            avg_ms = info.get("avg_duration_ms", 0) or 0
            with cols[i % len(cols)]:
                st.metric(
                    name.replace("_", " ").title(),
                    f"{status}",
                    f"avg {avg_ms:.0f}ms",
                )
