import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from database import init_db, async_session
from services.websocket_manager import ConnectionManager
from services.redis_consumer import RedisConsumer
from routers import health, detections, websockets

# Configure logging
logging.basicConfig(
    level=Config.get_log_level(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
manager = ConnectionManager()
consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    global consumer
    
    logger.info("Starting Earthquake Detection API...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize WebSocket manager for routers
    websockets.init_websocket_router(manager)
    
    # Create and start Redis consumer
    redis_url = Config.get_redis_url()
    consumer = RedisConsumer(redis_url, manager)
    
    # Start Redis consumer in background
    asyncio.create_task(consumer.start(async_session))
    logger.info("Redis consumer started")
    
    logger.info(f"Application startup complete - listening on {Config.HOST}:{Config.PORT}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    if consumer:
        await consumer.stop()
    
    logger.info("Application shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Earthquake Detection API",
    version=Config.API_VERSION,
    description="Real-time earthquake detection system comparing multiple ML models",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(detections.router)
app.include_router(websockets.router)

# Log registered routes on startup
@app.on_event("startup")
async def log_routes():
    logger.info("Registered routes:")
    for route in app.routes:
        if hasattr(route, "methods"):
            logger.info(f"  {route.methods} {route.path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level=Config.LOG_LEVEL.lower()
    )