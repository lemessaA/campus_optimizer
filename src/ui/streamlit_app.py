# src/ui/streamlit_app.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="Campus Operations Optimizer",
    page_icon="🎓",
    layout="wide"
)

# Title
st.title("🎓 Multi-Agent Campus Operations Optimization System")
st.markdown("---")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Schedule Optimization", "Equipment Booking", "Energy Insights"]

)

# src/ui/streamlit_app.py (add to existing)
# Add to the sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Schedule Optimization", "Equipment Booking", "Energy Insights", "Customer Support"]  # New tab
)

# Customer Support Page
elif page == "Customer Support":
    st.header("🆘 Customer Support Center")
    
    tab1, tab2, tab3 = st.tabs(["Ask a Question", "My Tickets", "Knowledge Base"])
    
    # Tab 1: Ask a Question
    with tab1:
        st.subheader("How can we help you today?")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            query = st.text_area("Type your question or issue", height=100,
                                 placeholder="e.g., How do I book a classroom?")
            
            if st.button("Get Help", type="primary"):
                with st.spinner("Searching for answers..."):
                    # Call support agent
                    response = make_api_request("POST", "/events", {
                        "event_type": "support_query",
                        "payload": {
                            "request_type": "faq_query",
                            "query": query,
                            "user_id": "current_user"
                        }
                    })
                
                if response and response.get("data"):
                    result = response["data"].get("results", {}).get("support", {})
                    
                    if result.get("status") == "success":
                        answer_data = result["data"]
                        
                        st.success("✅ Found an answer!")
                        
                        # Display answer
                        st.info(answer_data["answer"])
                        
                        if not answer_data.get("exact_match"):
                            st.caption(f"Confidence: {answer_data.get('confidence', 0):.0%}")
                        
                        # Feedback
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.button("👍 Helpful")
                        with col2:
                            st.button("👎 Not Helpful")
                        with col3:
                            st.button("📧 Email Answer")
                    
                    elif result.get("status") == "no_match":
                        st.warning("🤔 I couldn't find an exact match")
                        
                        # Show suggestion to create ticket
                        suggestion = result["data"]["suggested_ticket"]
                        st.info(f"**Suggested Category:** {suggestion['category'].title()}")
                        
                        if st.button("Create Support Ticket Instead"):
                            st.session_state['create_ticket'] = suggestion
        
        with col2:
            st.subheader("Quick Links")
            st.markdown("""
            - 📚 [Course Registration](#)
            - 🔬 [Lab Access](#)
            - 💡 [Energy Tips](#)
            - 📞 [Contact Support](#)
            """)
            
            st.subheader("Popular Topics")
            st.markdown("""
            - How to book equipment
            - Classroom availability
            - Report maintenance
            - Access issues
            """)
    
    # Tab 2: My Tickets
    with tab2:
        st.subheader("Your Support Tickets")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### Create New Ticket")
            
            with st.form("new_ticket"):
                category = st.selectbox(
                    "Category",
                    ["Select...", "Scheduling", "Equipment", "Facilities", "Energy", "Account"]
                )
                
                priority = st.select_slider(
                    "Priority",
                    options=["Low", "Medium", "High", "Urgent"],
                    value="Medium"
                )
                
                description = st.text_area("Description", height=100,
                                          placeholder="Describe your issue in detail...")
                
                submitted = st.form_submit_button("Submit Ticket")
                
                if submitted and category != "Select...":
                    with st.spinner("Creating ticket..."):
                        response = make_api_request("POST", "/events", {
                            "event_type": "ticket_creation",
                            "payload": {
                                "request_type": "create_ticket",
                                "category": category.lower(),
                                "description": description,
                                "priority": ["low", "medium", "high", "urgent"].index(priority.lower()) + 1,
                                "user_id": "current_user"
                            }
                        })
                    
                    if response:
                        ticket_data = response.get("data", {}).get("results", {}).get("support", {}).get("data", {})
                        st.success(f"✅ Ticket #{ticket_data.get('ticket_id')} created!")
                        st.info(f"Estimated resolution: {ticket_data.get('estimated_resolution')}")
        
        with col2:
            st.markdown("### Your Recent Tickets")
            
            # Mock ticket data
            tickets = [
                {"id": "TKT-001", "category": "Equipment", "status": "In Progress", "priority": "High", "created": "2024-01-15"},
                {"id": "TKT-002", "category": "Scheduling", "status": "Resolved", "priority": "Medium", "created": "2024-01-14"},
                {"id": "TKT-003", "category": "Facilities", "status": "Open", "priority": "Low", "created": "2024-01-13"},
            ]
            
            for ticket in tickets:
                with st.expander(f"Ticket #{ticket['id']} - {ticket['category']} ({ticket['status']})"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Priority", ticket['priority'])
                    with col2:
                        st.metric("Status", ticket['status'])
                    with col3:
                        st.metric("Created", ticket['created'])
                    
                    if st.button(f"Check Status", key=f"check_{ticket['id']}"):
                        st.info("Checking with support agent...")
    
    # Tab 3: Knowledge Base
    with tab3:
        st.subheader("Knowledge Base & FAQs")
        
        search = st.text_input("🔍 Search knowledge base", placeholder="Search for topics...")
        
        # Categories
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 📚 Scheduling")
            st.markdown("""
            - [How to book a classroom](#)
            - [Schedule changes](#)
            - [Room capacity guidelines](#)
            - [Exam scheduling](#)
            """)
        
        with col2:
            st.markdown("### 🔬 Equipment")
            st.markdown("""
            - [Booking procedure](#)
            - [Equipment training](#)
            - [Maintenance requests](#)
            - [Safety guidelines](#)
            """)
        
        with col3:
            st.markdown("### ⚡ Energy")
            st.markdown("""
            - [Energy saving tips](#)
            - [Peak hours](#)
            - [Green initiatives](#)
            - [Report issues](#)
            """)
        
        # Popular FAQs
        st.markdown("---")
        st.subheader("Frequently Asked Questions")
        
        faqs = [
            ("How do I book equipment?", "Visit Equipment Booking page, select item and time..."),
            ("What if my classroom is double-booked?", "Contact scheduling office immediately..."),
            ("How to report maintenance?", "Create a ticket in the support center..."),
            ("Energy saving tips?", "Check Energy Insights page for recommendations..."),
        ]
        
        for question, answer in faqs:
            with st.expander(question):
                st.write(answer)
                col1, col2 = st.columns(2)
                with col1:
                    st.button(f"👍 Helpful", key=f"helpful_{question[:10]}")
                with col2:
                    st.button(f"📌 Save", key=f"save_{question[:10]}")

# Helper functions
def make_api_request(method, endpoint, data=None):
    """Make API request with error handling"""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

# Dashboard Page
if page == "Dashboard":
    st.header("📊 System Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Active Classrooms", "24", "+2")
    with col2:
        st.metric("Equipment Available", "156", "-3")
    with col3:
        st.metric("Energy Savings Today", "245 kWh", "+12%")
    with col4:
        st.metric("Active Agents", "5", "Online")
    
    st.markdown("---")
    
    # Recent Events
    st.subheader("Recent System Events")
    
    # Mock data - would come from API
    events_data = pd.DataFrame({
        "Time": ["09:15", "09:30", "10:00", "10:30"],
        "Event": ["Course Added: CS101", "Equipment Booked: Microscope", "Empty Classroom Detected", "Energy Optimization Run"],
        "Status": ["✅ Scheduled", "✅ Approved", "⚡ Action Taken", "✅ Completed"],
        "Agent": ["Scheduling", "Equipment", "Energy", "Supervisor"]
    })
    
    st.dataframe(events_data, use_container_width=True)
    
    # Agent Status
    st.subheader("🤖 Agent Health")
    
    agent_status = pd.DataFrame({
        "Agent": ["Supervisor", "Scheduling", "Equipment", "Energy", "Notification"],
        "Status": ["🟢 Active", "🟢 Active", "🟡 Warning", "🟢 Active", "🟢 Active"],
        "Last Run": ["Now", "2 min ago", "5 min ago", "10 min ago", "1 min ago"],
        "Success Rate": ["100%", "98%", "95%", "99%", "100%"]
    })
    
    st.dataframe(agent_status, use_container_width=True)

# Schedule Optimization Page
elif page == "Schedule Optimization":
    st.header("📅 Classroom Schedule Optimization")
    
    # New Course Form
    with st.expander("➕ Add New Course", expanded=False):
        with st.form("new_course"):
            col1, col2 = st.columns(2)
            
            with col1:
                course_name = st.text_input("Course Name", placeholder="e.g., CS101")
                students = st.number_input("Number of Students", min_value=1, max_value=500)
            
            with col2:
                schedule_time = st.time_input("Schedule Time")
                building = st.selectbox("Preferred Building", ["All", "Engineering", "Science", "Arts"])
            
            submitted = st.form_submit_button("Submit Course")
            
            if submitted:
                course_data = {
                    "name": course_name,
                    "students_count": students,
                    "schedule_time": schedule_time.strftime("%H:%M"),
                    "duration_minutes": 60,
                    "preferred_building": building if building != "All" else None
                }
                
                with st.spinner("Optimizing schedule..."):
                    result = make_api_request("POST", "/courses", course_data)
                
                if result:
                    st.success(f"✅ Course submitted for optimization! Event ID: {result['data']['event_id']}")
    
    # Current Schedule
    st.subheader("Current Optimized Schedule")
    
    # Mock schedule data
    schedule_data = pd.DataFrame({
        "Time": ["09:00", "10:00", "11:00", "13:00", "14:00"],
        "Course": ["CS101", "MATH202", "PHY150", "ENG205", "CHEM101"],
        "Room": ["Hall A (100)", "Room 201 (50)", "Lab 1 (40)", "Room 305 (60)", "Lab 3 (30)"],
        "Building": ["Engineering", "Science", "Science", "Engineering", "Science"],
        "Utilization": ["85%", "92%", "88%", "78%", "95%"]
    })
    
    st.dataframe(schedule_data, use_container_width=True)
    
    # Visualization
    fig = px.bar(schedule_data, x="Time", y="Utilization", color="Building",
                 title="Room Utilization by Time Slot")
    st.plotly_chart(fig, use_container_width=True)

# Equipment Booking Page
elif page == "Equipment Booking":
    st.header("🔬 Lab Equipment Booking")
    
    # Booking Form
    with st.form("equipment_booking"):
        col1, col2 = st.columns(2)
        
        with col1:
            equipment = st.selectbox(
                "Select Equipment",
                ["Microscope (Lab 1)", "Centrifuge (Lab 2)", "Spectrometer (Lab 3)", "PCR Machine (Lab 4)"]
            )
            user_id = st.text_input("User ID / Email")
        
        with col2:
            booking_date = st.date_input("Date")
            booking_time = st.time_input("Start Time")
            duration = st.number_input("Duration (hours)", min_value=0.5, max_value=8.0, step=0.5)
        
        submitted = st.form_submit_button("Request Booking")
        
        if submitted:
            # Parse equipment ID
            equipment_id = equipment.split(" ")[0]
            
            booking_data = {
                "equipment_id": equipment_id,
                "user_id": user_id,
                "time_slot": datetime.combine(booking_date, booking_time).isoformat(),
                "duration_hours": duration
            }
            
            with st.spinner("Processing booking..."):
                result = make_api_request("POST", "/equipment/book", booking_data)
            
            if result:
                if result["status"] == "accepted":
                    st.success(f"✅ Booking request submitted! Event ID: {result['data']['event_id']}")
                else:
                    st.warning("⚠️ Booking requires review")
    
    # Equipment Status
    st.subheader("Equipment Availability")
    
    # Mock equipment data
    equipment_status = pd.DataFrame({
        "Equipment": ["Microscope A", "Centrifuge B", "Spectrometer C", "PCR Machine D", "Microscope B"],
        "Lab": ["Lab 1", "Lab 2", "Lab 3", "Lab 4", "Lab 1"],
        "Status": ["🟢 Available", "🟡 In Use", "🟢 Available", "🔴 Maintenance", "🟢 Available"],
        "Next Available": ["Now", "14:30", "Now", "Tomorrow", "Now"]
    })
    
    st.dataframe(equipment_status, use_container_width=True)

# Energy Insights Page
elif page == "Energy Insights":
    st.header("⚡ Energy Optimization Insights")
    
    # Refresh button
    if st.button("🔄 Refresh Insights"):
        with st.spinner("Analyzing energy patterns..."):
            insights = make_api_request("GET", "/energy/insights", None)
        
        if insights:
            st.session_state['energy_insights'] = insights
    
    # Display insights
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Savings (24h)", "245 kWh", "+8.2%")
    with col2:
        st.metric("Carbon Reduction", "98 kg CO2", "-12%")
    with col3:
        st.metric("Peak Period", "14:00 - 16:00", "High Load")
    
    st.markdown("---")
    
    # Energy Usage Chart
    st.subheader("Energy Consumption by Building")
    
    # Mock consumption data
    consumption_data = pd.DataFrame({
        "Hour": list(range(24)),
        "Engineering": [30 + i*5 for i in range(24)],
        "Science": [25 + i*4 for i in range(24)],
        "Arts": [15 + i*2 for i in range(24)]
    })
    
    fig = px.line(consumption_data, x="Hour", y=["Engineering", "Science", "Arts"],
                  title="Hourly Energy Consumption by Building")
    st.plotly_chart(fig, use_container_width=True)
    
    # Optimization Recommendations
    st.subheader("💡 Optimization Recommendations")
    
    recommendations = [
        {
            "action": "Reduce HVAC in empty Engineering labs",
            "savings": "45 kWh/day",
            "status": "✅ Active",
            "agent": "Energy Agent"
        },
        {
            "action": "Schedule equipment maintenance during off-peak",
            "savings": "30 kWh/day",
            "status": "🔄 Pending",
            "agent": "Equipment Agent"
        },
        {
            "action": "LED upgrade in Science building",
            "savings": "120 kWh/day",
            "status": "📅 Planned",
            "agent": "Energy Agent"
        }
    ]
    
    rec_df = pd.DataFrame(recommendations)
    st.dataframe(rec_df, use_container_width=True)
    
    # Agent Activity Log
    st.subheader("📋 Energy Agent Activity Log")
    
    log_data = pd.DataFrame({
        "Time": ["10:30", "10:15", "09:45", "09:30"],
        "Event": ["Empty classroom optimization", "Peak prediction run", "HVAC adjustment", "Scheduling optimization"],
        "Savings": ["12 kWh", "N/A", "25 kWh", "8 kWh"],
        "Status": ["✅ Completed", "✅ Completed", "✅ Completed", "✅ Completed"]
    })
    
    st.dataframe(log_data, use_container_width=True)