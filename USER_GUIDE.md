# 🎓 Campus Optimizer - User Guide

## 🚀 Getting Started

The Campus Optimizer is accessible through multiple interfaces:

### **1. Web Interface (Swagger UI)**
- **URL**: http://localhost:8000/docs
- **What**: Interactive API documentation
- **Best for**: Testing endpoints, exploring features

### **2. REST API**
- **Base URL**: http://localhost:8000/api/v1
- **What**: Programmatic access
- **Best for**: Applications, integrations

### **3. Health Check**
- **URL**: http://localhost:8000/health
- **What**: System status
- **Best for**: Monitoring, debugging

---

## 👥 User Types & Workflows

### **🎓 Students & Faculty**

#### **Create a Course**
```bash
curl -X POST http://localhost:8000/api/v1/courses \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Computer Science 101",
    "students_count": 30,
    "schedule_time": "09:00",
    "duration_minutes": 90,
    "preferred_building": "A"
  }'
```

**Response:**
```json
{
  "status": "accepted",
  "data": {
    "event_id": "48b24e3b-f34a-4435-bfd9-7b36f84819a8",
    "course_id": 5,
    "message": "Course creation submitted for optimization"
  },
  "error": null,
  "fallback_used": false
}
```

#### **View Schedule**
```bash
curl "http://localhost:8000/api/v1/schedule?building=A&date=2026-02-28"
```

#### **Book Equipment**
```bash
curl -X POST http://localhost:8000/api/v1/equipment/book \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": 1,
    "user_id": "student123",
    "time_slot": "2026-02-28T10:00:00",
    "duration_hours": 2
  }'
```

---

### **🏢 Facility Managers**

#### **Get Energy Insights**
```bash
curl http://localhost:8000/api/v1/energy/insights
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "event_id": "238f993e-0f8f-4b32-91b2-4bd120e180bf",
    "status": "completed",
    "results": {
      "energy": {
        "status": "success",
        "data": {
          "total_savings_24h": 7.5,
          "average_savings_per_action": 2.5,
          "peak_periods": [],
          "recommendations": [
            "Schedule heavy equipment use during off-peak hours",
            "Enable power saving mode in empty labs",
            "Consider upgrading to LED lighting in Building B"
          ]
        }
      }
    }
  }
}
```

#### **Trigger Energy Optimization**
```bash
curl -X POST "http://localhost:8000/api/v1/events?event_type=classroom_empty" \
  -H "Content-Type: application/json" \
  -d '{
    "building": "A",
    "classroom_id": 1
  }'
```

#### **Monitor Building Status**
```bash
curl -X POST "http://localhost:8000/api/v1/events?event_type=energy_optimization" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### **🔧 System Administrators**

#### **System Health Check**
```bash
curl http://localhost:8000/health
```

#### **Trigger Custom Events**
```bash
curl -X POST "http://localhost:8000/api/v1/events?event_type=timetable_updated" \
  -H "Content-Type: application/json" \
  -d '{
    "buildings": ["A", "B", "C"],
    "update_reason": "semester_change"
  }'
```

---

## 📱 Mobile/Web App Integration

### **Frontend Application Example**

```javascript
// React/Vue.js Component Example
class CampusOptimizer {
  constructor() {
    this.baseURL = 'http://localhost:8000/api/v1';
  }

  async createCourse(courseData) {
    const response = await fetch(`${this.baseURL}/courses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(courseData)
    });
    return await response.json();
  }

  async getEnergyInsights() {
    const response = await fetch(`${this.baseURL}/energy/insights`);
    return await response.json();
  }

  async bookEquipment(bookingData) {
    const response = await fetch(`${this.baseURL}/equipment/book`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookingData)
    });
    return await response.json();
  }

  async getSchedule(building, date) {
    const params = new URLSearchParams({ building, date });
    const response = await fetch(`${this.baseURL}/schedule?${params}`);
    return await response.json();
  }
}

// Usage
const campus = new CampusOptimizer();

// Create a course
await campus.createCourse({
  name: "Data Structures",
  students_count: 45,
  schedule_time: "14:00",
  duration_minutes: 120,
  preferred_building: "B"
});

// Get energy insights
const insights = await campus.getEnergyInsights();
console.log('Energy savings:', insights.data.results.energy.data.total_savings_24h);
```

---

## 📊 Dashboard Integration

### **Real-time Dashboard**

```javascript
// WebSocket for real-time updates (if implemented)
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateDashboard(data);
};

function updateDashboard(data) {
  // Update energy metrics
  document.getElementById('energy-savings').textContent = 
    `${data.energy_savings} kWh`;
  
  // Update classroom occupancy
  document.getElementById('occupied-rooms').textContent = 
    data.occupied_classrooms;
  
  // Update equipment status
  updateEquipmentList(data.equipment_status);
}
```

---

## 🔔 Notification System

### **Receive Notifications**

```javascript
// Poll for notifications
async function getNotifications() {
  const response = await fetch('http://localhost:8000/api/v1/notifications');
  const notifications = await response.json();
  
  notifications.forEach(notification => {
    showNotification(notification);
  });
}

// Display notification
function showNotification(notification) {
  const toast = document.createElement('div');
  toast.className = 'notification';
  toast.innerHTML = `
    <h4>${notification.type}</h4>
    <p>${notification.message}</p>
    <small>${notification.timestamp}</small>
  `;
  document.body.appendChild(toast);
}
```

---

## 🎯 Common User Workflows

### **1. Professor Creating a New Course**

1. **Access**: Web portal or mobile app
2. **Action**: Fill course creation form
3. **System**: 
   - Validates course data
   - Finds optimal classroom
   - Schedules energy optimization
   - Sends confirmation
4. **Result**: Course scheduled with room assignment

### **2. Student Booking Lab Equipment**

1. **Access**: Mobile app
2. **Action**: Select equipment and time
3. **System**:
   - Checks availability
   - Detects conflicts
   - Creates booking
   - Sends notification
4. **Result**: Equipment reserved

### **3. Facility Manager Monitoring Energy**

1. **Access**: Dashboard
2. **Action**: View energy insights
3. **System**:
   - Analyzes consumption patterns
   - Identifies savings opportunities
   - Provides recommendations
4. **Result**: Actionable energy insights

---

## 🛠️ API Reference

### **Authentication (Future)**
```bash
# With API Key (if implemented)
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/api/v1/courses
```

### **Error Handling**
```javascript
try {
  const result = await campus.createCourse(courseData);
  if (result.status === 'accepted') {
    showSuccess('Course created successfully!');
  }
} catch (error) {
  showError('Failed to create course: ' + error.message);
}
```

### **Rate Limiting**
- **Current**: No limits (development)
- **Production**: 100 requests/minute per user

---

## 📱 Mobile App Features

### **Student App**
- ✅ Course schedule viewing
- ✅ Equipment booking
- ✅ Classroom availability
- ✅ Real-time notifications

### **Faculty App**
- ✅ Course management
- ✅ Schedule optimization
- ✅ Resource allocation
- ✅ Analytics dashboard

### **Admin App**
- ✅ System monitoring
- ✅ Energy management
- ✅ Facility control
- ✅ User management

---

## 🚀 Getting Help

### **Documentation**
- **Swagger UI**: http://localhost:8000/docs
- **API Schema**: http://localhost:8000/openapi.json

### **Support**
- **Health Check**: http://localhost:8000/health
- **Logs**: Check server console for detailed logs
- **Debug**: Use Swagger UI "Try it out" feature

---

## 🎯 Best Practices

1. **Always check response status** before processing data
2. **Handle errors gracefully** with user-friendly messages
3. **Use background tasks** for long-running operations
4. **Cache responses** when appropriate
5. **Validate input** before sending to API
6. **Monitor system health** regularly

---

**🎓 Ready to optimize your campus!**
