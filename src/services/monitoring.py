# src/services/monitoring.py
import logging
import sys
from datetime import datetime
from src.core.config import settings

# Configure logging
def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('campus_optimizer.log')
        ]
    )

logger = logging.getLogger(__name__)

async def health_check():
    """Health check for system monitoring"""
    from src.services.database import check_db_connection
    from src.services.cache import check_redis_connection
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if await check_db_connection() else "disconnected",
        "redis": "connected" if await check_redis_connection() else "disconnected",
        "agents": {
            "supervisor": "active",
            "scheduling": "active",
            "equipment": "active",
            "energy": "active",
            "notification": "active"
        }
    }