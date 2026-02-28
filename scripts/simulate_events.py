# scripts/simulate_events.py
#!/usr/bin/env python3
"""
Simulation script to demonstrate the multi-agent system
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta
import requests
import time

API_BASE = "http://localhost:8000/api/v1"

def simulate_campus_day():
    """Simulate a day of campus operations"""
    print("🎓 Starting Campus Operations Simulation")
    print("=" * 50)
    
    # Simulate course creations
    courses = [
        {"name": "CS101", "students": 45, "time": "09:00", "building": "Engineering"},
        {"name": "MATH202", "students": 60, "time": "10:00", "building": "Science"},
        {"name": "PHY150", "students": 30, "time": "11:00", "building": "Science"},
        {"name": "ENG205", "students": 55, "time": "13:00", "building": "Engineering"},
        {"name": "CHEM101", "students": 40, "time": "14:00", "building": "Science"},
    ]
    
    print("\n📚 Adding courses...")
    for course in courses:
        response = requests.post(
            f"{API_BASE}/courses",
            json={
                "name": course["name"],
                "students_count": course["students"],
                "schedule_time": course["time"],
                "duration_minutes": 60,
                "preferred_building": course["building"]
            }
        )
        if response.status_code == 200:
            print(f"  ✅ {course['name']} added - Event ID: {response.json()['data']['event_id']}")
        time.sleep(0.5)
    
    # Simulate equipment bookings
    print("\n🔬 Processing equipment bookings...")
    equipment_items = [1, 2, 3, 4, 5]  # Equipment IDs
    
    for i in range(3):
        booking = {
            "equipment_id": random.choice(equipment_items),
            "user_id": f"user_{random.randint(100, 999)}",
            "time_slot": (datetime.now() + timedelta(hours=random.randint(1, 24))).isoformat(),
            "duration_hours": random.randint(1, 3)
        }
        
        response = requests.post(f"{API_BASE}/equipment/book", json=booking)
        if response.status_code == 200:
            print(f"  ✅ Booking request for equipment {booking['equipment_id']} submitted")
        time.sleep(0.5)
    
    # Get energy insights
    print("\n⚡ Analyzing energy optimization...")
    response = requests.get(f"{API_BASE}/energy/insights")
    if response.status_code == 200:
        insights = response.json()
        print(f"  ✅ Energy analysis complete")
        if insights.get('data') and insights['data'].get('results'):
            results = insights['data']['results']
            if 'energy' in results:
                energy_data = results['energy'].get('data', {})
                print(f"     Total savings: {energy_data.get('total_savings_24h', 'N/A')} kWh")
    
    print("\n" + "=" * 50)
    print("✨ Simulation complete!")

if __name__ == "__main__":
    simulate_campus_day()