# src/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List
import uuid

from src.api.routes import router
from src.api.dependencies import set_supervisor
from src.core.config import settings
from src.services.database import init_db, close_db
from src.services.cache import init_redis, close_redis
from src.services.monitoring import setup_logging
from src.agents.supervisor_agent import SupervisorAgent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup and shutdown events"""
    # Startup
    setup_logging()
    await init_db()
    await init_redis()
    
    # Initialize and set supervisor agent
    supervisor = SupervisorAgent()
    set_supervisor(supervisor)
    
    yield
    
    # Shutdown
    await close_db()
    await close_redis()

# Create FastAPI app
app = FastAPI(
    title="Campus Operations Optimization System",
    description="Multi-Agent System for Smart Campus Management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}