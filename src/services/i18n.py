# src/services/i18n.py
from typing import Dict, Any, Optional
import json
from pathlib import Path
from fastapi import Request
from src.services.monitoring import logger

class I18nService:
    """Internationalization service for multi-language support"""
    
    def __init__(self):
        self.translations_dir = Path("translations")
        self.translations_dir.mkdir(exist_ok=True)
        
        # Supported languages
        self.supported_languages = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "zh": "Chinese",
            "ja": "Japanese",
            "ar": "Arabic",
            "hi": "Hindi"
        }
        
        # Default language
        self.default_language = "en"
        
        # Load translations
        self.translations = self.load_all_translations()
    
    def load_all_translations(self) -> Dict[str, Dict]:
        """Load all translation files"""
        translations = {}
        
        for lang_code in self.supported_languages.keys():
            lang_file = self.translations_dir / f"{lang_code}.json"
            
            if lang_file.exists():
                with open(lang_file, 'r', encoding='utf-8') as f:
                    translations[lang_code] = json.load(f)
            else:
                # Create empty translation file
                translations[lang_code] = {}
                self.save_translations(lang_code, {})
        
        return translations
    
    def save_translations(self, lang_code: str, translations: Dict):
        """Save translations to file"""
        lang_file = self.translations_dir / f"{lang_code}.json"
        
        with open(lang_file, 'w', encoding='utf-8') as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)
    
    def get_text(self, key: str, lang_code: str = None, **kwargs) -> str:
        """Get translated text for key"""
        if not lang_code or lang_code not in self.translations:
            lang_code = self.default_language
        
        # Get translation
        text = self.translations[lang_code].get(key)
        
        if not text:
            # Fall back to English
            text = self.translations["en"].get(key, key)
        
        # Format with variables
        if kwargs:
            try:
                text = text.format(**kwargs)
            except:
                pass
        
        return text
    
    def detect_language(self, request: Request) -> str:
        """Detect user's preferred language"""
        # Check Accept-Language header
        accept_language = request.headers.get("accept-language", "")
        
        # Parse Accept-Language
        languages = []
        for lang in accept_language.split(","):
            parts = lang.split(";q=")
            code = parts[0].strip().split("-")[0]  # Get primary language code
            quality = float(parts[1]) if len(parts) > 1 else 1.0
            languages.append((code, quality))
        
        # Sort by quality
        languages.sort(key=lambda x: x[1], reverse=True)
        
        # Find first supported language
        for code, _ in languages:
            if code in self.supported_languages:
                return code
        
        return self.default_language
    
    def add_translation(self, lang_code: str, key: str, value: str):
        """Add or update a translation"""
        if lang_code not in self.translations:
            self.translations[lang_code] = {}
        
        self.translations[lang_code][key] = value
        self.save_translations(lang_code, self.translations[lang_code])
        
        logger.info(f"Added translation: {lang_code}.{key}")
    
    def export_translation_template(self) -> Dict:
        """Export all keys in English as template"""
        return self.translations["en"]
    
    def translate_faq(self, faq_id: int, target_lang: str) -> Optional[Dict]:
        """Translate FAQ to target language. Returns None when translation is not available.
        In production, wire this to a translation API (e.g. Google Translate, DeepL) or
        use pre-stored translations from DB/cache."""
        # No translation service configured: callers should show original FAQ
        return None

# Language middleware
from starlette.middleware.base import BaseHTTPMiddleware

class LanguageMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.i18n = I18nService()
    
    async def dispatch(self, request: Request, call_next):
        # Detect language
        lang = request.headers.get("X-Language") or self.i18n.detect_language(request)
        
        # Add to request state
        request.state.lang = lang
        
        # Process request
        response = await call_next(request)
        
        # Add language header
        response.headers["Content-Language"] = lang
        
        return response

# Template for translations file
TRANSLATION_TEMPLATE = {
    "en": {
        # Navigation
        "nav.dashboard": "Dashboard",
        "nav.schedule": "Schedule Optimization",
        "nav.equipment": "Equipment Booking",
        "nav.energy": "Energy Insights",
        "nav.support": "Customer Support",
        
        # Common
        "common.submit": "Submit",
        "common.cancel": "Cancel",
        "common.save": "Save",
        "common.delete": "Delete",
        "common.edit": "Edit",
        "common.search": "Search",
        "common.loading": "Loading...",
        "common.error": "Error",
        "common.success": "Success",
        "common.warning": "Warning",
        
        # Dashboard
        "dashboard.title": "System Overview",
        "dashboard.active_classrooms": "Active Classrooms",
        "dashboard.equipment_available": "Equipment Available",
        "dashboard.energy_savings": "Energy Savings Today",
        "dashboard.active_agents": "Active Agents",
        
        # Schedule
        "schedule.title": "Classroom Schedule Optimization",
        "schedule.add_course": "Add New Course",
        "schedule.course_name": "Course Name",
        "schedule.students": "Number of Students",
        "schedule.time": "Schedule Time",
        "schedule.building": "Preferred Building",
        "schedule.current": "Current Optimized Schedule",
        
        # Equipment
        "equipment.title": "Lab Equipment Booking",
        "equipment.select": "Select Equipment",
        "equipment.user_id": "User ID / Email",
        "equipment.date": "Date",
        "equipment.time": "Start Time",
        "equipment.duration": "Duration (hours)",
        "equipment.request": "Request Booking",
        "equipment.status": "Equipment Status",
        
        # Energy
        "energy.title": "Energy Optimization Insights",
        "energy.savings": "Total Savings (24h)",
        "energy.carbon": "Carbon Reduction",
        "energy.peak": "Peak Period",
        "energy.consumption": "Energy Consumption by Building",
        "energy.recommendations": "Optimization Recommendations",
        
        # Support
        "support.title": "Customer Support Center",
        "support.ask": "Ask a Question",
        "support.tickets": "My Tickets",
        "support.knowledge": "Knowledge Base",
        "support.query_placeholder": "Type your question or issue...",
        "support.get_help": "Get Help",
        "support.create_ticket": "Create Support Ticket",
        "support.category": "Category",
        "support.priority": "Priority",
        "support.description": "Description",
        
        # Ticket priorities
        "priority.low": "Low",
        "priority.medium": "Medium",
        "priority.high": "High",
        "priority.urgent": "Urgent",
        
        # Error messages
        "error.required": "This field is required",
        "error.invalid_email": "Invalid email address",
        "error.booking_conflict": "Time slot not available",
        "error.server_error": "Server error. Please try again later.",
        
        # Success messages
        "success.course_added": "Course added successfully",
        "success.booking_confirmed": "Booking confirmed",
        "success.ticket_created": "Ticket created successfully",
        
        # Agent names
        "agent.supervisor": "Supervisor",
        "agent.scheduling": "Scheduling",
        "agent.equipment": "Equipment",
        "agent.energy": "Energy",
        "agent.notification": "Notification",
        "agent.support": "Support"
    }
}