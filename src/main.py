# src/main.py - Simplified version with existing routers/services
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.services.monitoring import setup_logging
setup_logging()

from src.api import auth_routes
from src.api.routes import router as api_router
from src.api.dependencies import set_supervisor
from src.agents.supervisor_agent import SupervisorAgent
from src.services.database import init_db, close_db
from src.services.cache import init_redis, close_redis
from src.services.monitoring import health_check

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    
    # Initialize database
    await init_db()
    
    # Initialize Redis
    await init_redis()
    
    # Initialize agents
    supervisor = SupervisorAgent()
    set_supervisor(supervisor)
    
    yield
    
    # Cleanup
    await close_db()
    await close_redis()

# Create FastAPI app
app = FastAPI(
    title="Campus Operations Optimization System",
    description="Multi-Agent System for Smart Campus Management",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def get_health():
    return await health_check()