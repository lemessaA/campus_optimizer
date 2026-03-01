# src/ui/streamlit_app.py
"""Campus Operations Optimizer — Multi-agent scheduling, equipment, energy & support."""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from urllib.parse import urlencode

import sys
from pathlib import Path
# Ensure project root is in path for imports
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.ui.components import (
    inject_global_styles,
    page_header,
    metric_row,
    render_table,
    form_card,
    empty_state,
    agent_status_list,
    insight_list,
    recommendation_list,
    bar_chart,
    line_chart,
    tab_page,
)

import os
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
HEALTH_URL = os.getenv("HEALTH_URL", "http://localhost:8000/health")


def make_api_request(method: str, endpoint: str, data=None, *, params=None):
    """Call API with error handling. For GET, pass params= as keyword argument."""
    url = f"{API_BASE_URL}{endpoint}"
    if params and method == "GET":
        sep = "&" if "?" in endpoint else "?"
        url = f"{url}{sep}{urlencode(params)}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=15)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API error: {str(e)}")
        return None


# --- Page config (must be first Streamlit command)
st.set_page_config(
    page_title="Campus Operations Optimizer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Global styles
inject_global_styles()

# --- Sidebar navigation
with st.sidebar:
    st.markdown("## 🎓 Campus Optimizer")
    st.caption("Multi-agent operations")
    st.markdown("---")
    st.markdown("**Overview**")
    nav = st.radio(
        "Page",
        ["Dashboard", "Schedule", "Equipment", "Energy", "Support", "Analytics"],
        label_visibility="collapsed",
        key="nav",
    )
    st.markdown("---")
    st.caption("API")
    st.code(API_BASE_URL, language=None)
    if st.sidebar.button("Check health"):
        try:
            health = requests.get(HEALTH_URL, timeout=5).json()
        except Exception:
            health = None
    else:
        health = None
    if health:
        st.success("API OK" if health.get("status") == "healthy" else "API issue")

PAGES = {
    "Dashboard": "dashboard",
    "Schedule": "schedule",
    "Equipment": "equipment",
    "Energy": "energy",
    "Support": "support",
    "Analytics": "analytics",
}
page = PAGES.get(nav, "dashboard")


# ========== DASHBOARD ==========
if page == "dashboard":
    page_header("Dashboard", "Live metrics and recent activity", icon="📊")

    metrics = make_api_request("GET", "/dashboard/metrics")
    if not metrics:
        empty_state("Start the API to see metrics.", icon="⚠️")
    else:
        metric_row([
            ("Classrooms booked today", metrics.get("classrooms_booked_today", 0)),
            ("Equipment available", metrics.get("equipment_available", 0)),
            ("Energy savings (24h)", f"{metrics.get('energy_savings_today_kwh', 0)} kWh"),
            ("Active agents", sum(1 for v in (metrics.get("agents") or {}).values() if v == "active")),
        ])
        st.markdown("---")
        st.subheader("Recent activity")
        activity = make_api_request("GET", "/dashboard/recent_activity")
        if activity and activity.get("activities"):
            render_table(
                activity["activities"],
                column_map={"time": "Time", "event": "Event", "status": "Status", "agent": "Agent"},
                display_columns=["Time", "Event", "Status", "Agent"],
            )
        else:
            empty_state(
                "No recent activity.",
                action_hint="Create courses, book equipment, or run energy optimization.",
            )
        st.subheader("Agent status")
        if metrics.get("agents"):
            agent_status_list(metrics["agents"])


# ========== SCHEDULE ==========
elif page == "schedule":
    page_header("Schedule optimization", "Add courses and view optimized classroom assignments", icon="📅")

    with form_card("Add new course", expanded=False, icon="➕"):
        course_name = st.text_input("Course name", placeholder="e.g. CS101")
        col1, col2 = st.columns(2)
        with col1:
            students = st.number_input("Students", min_value=1, max_value=500, value=50)
            schedule_time = st.time_input("Time")
        with col2:
            building = st.selectbox("Building", ["All", "Engineering", "Science", "Arts"])
        if st.form_submit_button("Submit"):
            if not course_name:
                st.error("Course name required")
            else:
                result = make_api_request("POST", "/courses", {
                    "name": course_name,
                    "students_count": students,
                    "schedule_time": schedule_time.strftime("%H:%M"),
                    "duration_minutes": 60,
                    "preferred_building": building if building != "All" else None,
                })
                if result and result.get("data"):
                    st.success(f"Course submitted. Event: {result['data'].get('event_id', '—')}")

    st.subheader("Current schedule")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        schedule_date = st.date_input("Date", value=datetime.now().date(), key="sched_date")
    with col2:
        schedule_building = st.selectbox("Building", ["All", "Engineering", "Science", "Arts"], key="sched_bld")
    with col3:
        refresh = st.button("Refresh")

    if refresh:
        st.session_state.pop("schedule_entries", None)

    if "schedule_entries" not in st.session_state:
        params = {"date": schedule_date.strftime("%Y-%m-%d")}
        if schedule_building != "All":
            params["building"] = schedule_building
        st.session_state["schedule_entries"] = make_api_request("GET", "/schedule/entries", params=params)

    entries = st.session_state.get("schedule_entries")
    if not entries:
        empty_state("No schedule entries.", action_hint="Add a course above.")
    else:
        column_map = {
            "time": "Time", "course_name": "Course", "classroom_name": "Room",
            "building": "Building", "students_count": "Students",
            "classroom_capacity": "Capacity", "utilization_rate": "Utilization",
        }
        df = pd.DataFrame(entries).rename(columns=column_map)
        if "Utilization" in df.columns:
            df["Utilization %"] = (df["Utilization"] * 100).round(0).astype(int).astype(str) + "%"
        st.dataframe(df, use_container_width=True)
        if "Utilization" in df.columns and not df.empty:
            bar_chart(df, "Time", "Utilization", "Building", "Utilization by slot", y_format="percent")


# ========== EQUIPMENT ==========
elif page == "equipment":
    page_header("Equipment booking", "Request lab equipment and view bookings", icon="🔬")

    if st.button("Refresh equipment"):
        st.session_state.pop("equipment_list", None)
        st.session_state.pop("equipment_bookings", None)

    equipment_list = st.session_state.get("equipment_list")
    if equipment_list is None:
        equipment_list = make_api_request("GET", "/equipment") or []
        st.session_state["equipment_list"] = equipment_list

    equipment_options = {f"{e.get('name')} ({e.get('lab')}) — {e.get('status')}": e.get("id") for e in (equipment_list or []) if e.get("id")}

    with form_card("New booking", expanded=True, icon="📅"):
        col1, col2 = st.columns(2)
        with col1:
            equipment_label = st.selectbox("Equipment", list(equipment_options.keys()) or ["No equipment loaded"])
            user_id = st.text_input("User ID / email")
        with col2:
            booking_date = st.date_input("Date")
            booking_time = st.time_input("Start time")
            duration = st.number_input("Duration (hours)", min_value=0.5, max_value=8.0, step=0.5)
        if st.form_submit_button("Request booking"):
            eid = equipment_options.get(equipment_label) if equipment_options else None
            if not eid:
                st.error("Select equipment and ensure API is running.")
            else:
                result = make_api_request("POST", "/equipment/book", {
                    "equipment_id": eid,
                    "user_id": user_id or "guest",
                    "time_slot": datetime.combine(booking_date, booking_time).isoformat(),
                    "duration_hours": duration,
                })
                if result and result.get("status") == "accepted":
                    st.success(f"Booking submitted. Event: {result.get('data', {}).get('event_id', '—')}")
                    st.session_state.pop("equipment_bookings", None)

    st.subheader("Recent bookings")
    bookings = st.session_state.get("equipment_bookings")
    if bookings is None:
        bookings = make_api_request("GET", "/equipment/bookings", params={"limit": 50}) or []
        st.session_state["equipment_bookings"] = bookings
    if not bookings:
        empty_state("No bookings yet.")
    else:
        column_map = {"equipment_name": "Equipment", "user_id": "User", "start_time": "Start", "end_time": "End"}
        render_table(bookings, column_map=column_map, display_columns=["Equipment", "User", "Start", "End"], max_rows=20)


# ========== ENERGY ==========
elif page == "energy":
    page_header("Energy insights", "Savings, consumption, and recommendations", icon="⚡")

    if st.button("Refresh insights"):
        st.session_state.pop("energy_insights", None)
        st.session_state.pop("energy_consumption", None)
        st.session_state.pop("energy_logs", None)

    insights_raw = st.session_state.get("energy_insights")
    if insights_raw is None:
        with st.spinner("Loading insights…"):
            insights_raw = make_api_request("GET", "/energy/insights")
        st.session_state["energy_insights"] = insights_raw

    energy_data = None
    energy_message = None
    if isinstance(insights_raw, dict) and insights_raw.get("data"):
        res = insights_raw["data"].get("results") or {}
        if isinstance(res.get("energy"), dict):
            energy_result = res["energy"]
            energy_data = energy_result.get("data") or {}
            energy_message = energy_result.get("message") or energy_result.get("summary")

    if energy_message:
        st.info(energy_message)
    if energy_data:
        metric_row([
            ("Savings (24h)", f"{float(energy_data.get('total_savings_24h') or 0):.1f} kWh"),
            ("Carbon reduction", f"{float(energy_data.get('total_savings_24h') or 0) * 0.4:.1f} kg CO₂"),
            ("Peak periods", ", ".join(p.get("hour", "") for p in (energy_data.get("peak_periods") or [])[:3]) or "—"),
        ])
    else:
        empty_state("Run the API and refresh to load energy insights.")

    st.subheader("Consumption (24h)")
    consumption = st.session_state.get("energy_consumption")
    if consumption is None:
        consumption = make_api_request("GET", "/energy/consumption", params={"hours": 24}) or []
        st.session_state["energy_consumption"] = consumption
    if consumption:
        cdf = pd.DataFrame(consumption)
        if "timestamp" in cdf.columns and "consumption" in cdf.columns:
            cdf["timestamp"] = pd.to_datetime(cdf["timestamp"])
            line_chart(cdf, "timestamp", "consumption", "building" if "building" in cdf.columns else None, "Consumption")
    else:
        empty_state("No consumption data yet.")

    if energy_data and energy_data.get("recommendations"):
        st.subheader("Recommendations")
        recommendation_list(energy_data["recommendations"])

    st.subheader("Activity log")
    logs = st.session_state.get("energy_logs")
    if logs is None:
        logs = make_api_request("GET", "/energy/logs", params={"hours": 24, "limit": 200}) or []
        st.session_state["energy_logs"] = logs
    if logs:
        render_table(logs)
    else:
        empty_state("No energy logs yet.")


# ========== ANALYTICS ==========
elif page == "analytics":
    page_header("App Analytics", "Analytics, health, and insights from analysis agents", icon="📈")

    def _analytics_tab():
        st.subheader("Usage & performance analytics")
        report_type = st.selectbox("Report type", ["full", "usage", "performance", "trends"], key="analytics_type")
        if st.button("Run analytics", key="run_analytics"):
            with st.spinner("Analyzing…"):
                resp = make_api_request("GET", "/analytics/report", params={"report_type": report_type})
            if resp and resp.get("data"):
                st.json(resp["data"])
                if resp["data"].get("summary"):
                    st.info(resp["data"]["summary"])
            else:
                st.error("Analytics failed or no data.")

    def _health_tab():
        st.subheader("System & agent health")
        health_type = st.selectbox("Report type", ["full", "agents", "infrastructure"], key="health_type")
        if st.button("Run health check", key="run_health"):
            with st.spinner("Checking health…"):
                resp = make_api_request("GET", "/health/report", params={"report_type": health_type})
            if resp and resp.get("data"):
                data = resp["data"]
                if data.get("overall"):
                    st.metric("Overall status", data["overall"])
                if data.get("agents"):
                    for agent, info in data["agents"].items():
                        st.markdown(f"- **{agent}**: {info.get('status', '—')} (avg {info.get('avg_duration_ms', 0):.0f}ms)")
                if data.get("issues"):
                    for issue in data["issues"]:
                        st.warning(issue)
                st.json(data)
            else:
                st.error("Health check failed.")

    def _insights_tab():
        st.subheader("Predictive insights")
        domain = st.selectbox("Domain", ["all", "scheduling", "energy", "equipment"], key="insights_domain")
        if st.button("Get insights", key="run_insights"):
            with st.spinner("Generating insights…"):
                resp = make_api_request("GET", "/insights", params={"domain": domain})
            if resp and resp.get("data"):
                data = resp["data"]
                insights = data.get("insights") or []
                insight_list(insights)
                if data.get("summary"):
                    st.info(data["summary"])
                st.json(data)
            else:
                st.error("Insights failed.")

    def _dashboard_tab():
        st.subheader("Aggregated dashboard analysis")
        if st.button("Load full analysis", key="run_dashboard_analysis"):
            with st.spinner("Loading analytics, health, and insights…"):
                resp = make_api_request("GET", "/dashboard/analysis")
            if resp:
                st.json(resp)
            else:
                st.error("Dashboard analysis failed.")

    tab_page([
        ("Analytics Report", _analytics_tab),
        ("Health Report", _health_tab),
        ("Insights", _insights_tab),
        ("Dashboard Analysis", _dashboard_tab),
    ])


# ========== SUPPORT ==========
else:
    page_header("Customer support", "Ask questions, create tickets, browse FAQs", icon="💬")

    def _query_tab():
        st.subheader("Ask a question")
        query = st.text_area("Your question", placeholder="e.g. How do I book a classroom?", height=100)
        if st.button("Get answer", type="primary"):
            if not query.strip():
                st.warning("Enter a question.")
            else:
                resp = make_api_request("POST", "/support/query", {"query": query.strip(), "user_id": "ui_user"})
                if resp and resp.get("status") == "success" and resp.get("data"):
                    data = resp["data"]
                    results = data.get("results") or {}
                    support_result = results.get("support") or {}
                    support_data = (support_result.get("data") or {}) if isinstance(support_result, dict) else {}
                    if support_result.get("status") == "success" and support_data.get("answer"):
                        st.success("Answer")
                        st.info(support_data["answer"])
                    elif support_result.get("status") == "no_match":
                        st.warning("No exact match.")
                        sug = support_data.get("suggested_ticket") or {}
                        st.caption(f"Suggested category: {sug.get('category', '—')}. Create a ticket in the Tickets tab.")
                    else:
                        st.info("No answer found. Try the FAQs or create a ticket.")
                else:
                    st.error("Request failed or no data.")

    def _tickets_tab():
        st.subheader("Create ticket")
        with form_card("New ticket", expanded=True):
            category = st.selectbox("Category", ["scheduling", "equipment", "facilities", "energy", "account"])
            priority = st.select_slider("Priority", options=["low", "medium", "high", "urgent"], value="medium")
            description = st.text_area("Description", placeholder="Describe the issue…")
            if st.form_submit_button("Submit"):
                if not description.strip():
                    st.error("Description required.")
                else:
                    prio_map = {"low": 1, "medium": 2, "high": 3, "urgent": 4}
                    resp = make_api_request("POST", "/support/tickets", {
                        "category": category,
                        "description": description.strip(),
                        "priority": prio_map.get(priority, 2),
                        "user_id": "ui_user",
                    })
                    if resp and resp.get("status") == "success" and resp.get("data"):
                        res = resp["data"].get("results") or {}
                        sup = res.get("support") or {}
                        sup_data = sup.get("data") or {} if isinstance(sup, dict) else {}
                        st.success(f"Ticket created. ID: {sup_data.get('ticket_id', '—')}")
                        st.session_state.pop("support_tickets", None)

        st.subheader("Your tickets")
        if st.button("Refresh tickets"):
            st.session_state.pop("support_tickets", None)
        raw = make_api_request("GET", "/support/tickets", params={"user_id": "ui_user", "limit": 50})
        tickets = raw if isinstance(raw, list) else (raw.get("data") if isinstance(raw, dict) else []) or []
        if not tickets:
            empty_state("No tickets.")
        else:
            for t in tickets:
                with st.expander(f"#{t.get('id')} — {t.get('category')} ({t.get('status')})"):
                    st.write(f"Priority: {t.get('priority')} | Created: {t.get('created_at')}")
                    if t.get("updated_at"):
                        st.caption(f"Updated: {t.get('updated_at')}")

    def _faq_tab():
        st.subheader("Knowledge base")
        if st.button("Refresh FAQs"):
            st.session_state.pop("support_faqs", None)
        faqs = st.session_state.get("support_faqs")
        if faqs is None:
            faqs = make_api_request("GET", "/support/faqs") or []
            st.session_state["support_faqs"] = faqs
        search = st.text_input("Search", placeholder="Filter by keyword…")
        if search:
            q = search.lower()
            faqs = [f for f in (faqs or []) if q in (f.get("question") or "").lower() or q in (f.get("answer") or "").lower()]
        if not faqs:
            empty_state("No FAQs.", action_hint="Populate Redis key support:faqs to show content.")
        else:
            for faq in faqs:
                with st.expander(f"{faq.get('question') or 'Question'} ({faq.get('category', 'general')})"):
                    st.write(faq.get("answer") or "")

    tab_page([
        ("Ask", _query_tab),
        ("Tickets", _tickets_tab),
        ("FAQs", _faq_tab),
    ])
