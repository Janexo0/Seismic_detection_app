import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from database import engine, get_db, init_db
from schemas import DetectionResponse, DetectionCreate, ComparisonResult
from models import Detection
from sqlalchemy import select, and_
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "waveforms": [],
            "detections": []
        }

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        self.active_connections[channel].append(websocket)
        logger.info(f"Client connected to {channel} channel")

    def disconnect(self, websocket: WebSocket, channel: str):
        self.active_connections[channel].remove(websocket)
        logger.info(f"Client disconnected from {channel} channel")

    async def broadcast(self, message: dict, channel: str):
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections[channel].remove(conn)

manager = ConnectionManager()

# Redis consumer task
class RedisConsumer:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
        self.pubsub = None
        self.running = False
        self.detection_cache = {}  # Cache detections by event_id
        
    async def connect(self):
        self.redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        self.pubsub = self.redis.pubsub()
        
    async def subscribe_waveforms(self):
        """Subscribe to seismic waveform data and broadcast to WebSocket clients"""
        await self.pubsub.subscribe("seismic:waveforms")
        logger.info("Subscribed to seismic:waveforms")
        
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    
                    # Transform for WebSocket
                    ws_message = {
                        "type": "waveform",
                        "event_id": data["event_id"],
                        "timestamp": data["timestamp"],
                        "station": data["station"],
                        "data": data["waveform"]["data"][:1000],  # Limit data size
                        "sampling_rate": data["sampling_rate"]
                    }
                    
                    await manager.broadcast(ws_message, "waveforms")
                    
                except Exception as e:
                    logger.error(f"Error processing waveform: {e}")
    
    async def subscribe_detections(self, db_session_factory):
        """Subscribe to detection results and broadcast to WebSocket clients"""
        await self.pubsub.subscribe("detections:results")
        logger.info("Subscribed to detections:results")
        
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    event_id = data["event_id"]
                    model_name = data["model_name"]
                    
                    # Cache detection by event_id and model
                    if event_id not in self.detection_cache:
                        self.detection_cache[event_id] = {}
                    
                    self.detection_cache[event_id][model_name] = data
                    
                    # Check if we have results from both models
                    if len(self.detection_cache[event_id]) == 2:
                        # We have both models' results
                        results = self.detection_cache[event_id]
                        
                        # Create comparison
                        comparison = self.compare_detections(results)
                        
                        # Persist to database
                        await self.persist_detections(results, comparison, db_session_factory)
                        
                        # Broadcast to WebSocket
                        ws_message = {
                            "type": "detection",
                            "event_id": event_id,
                            "timestamp": data["detection_timestamp"],
                            "models": results,
                            "comparison": comparison
                        }
                        
                        await manager.broadcast(ws_message, "detections")
                        
                        # Clean up cache
                        del self.detection_cache[event_id]
                    
                except Exception as e:
                    logger.error(f"Error processing detection: {e}")
    
    def compare_detections(self, results: Dict) -> Dict:
        """Compare detection results from both models"""
        models = list(results.keys())
        if len(models) != 2:
            return {}
        
        model_a, model_b = models[0], models[1]
        
        detected_a = results[model_a]["detected"]
        detected_b = results[model_b]["detected"]
        conf_a = results[model_a]["confidence"]
        conf_b = results[model_b]["confidence"]
        
        return {
            "agreement": detected_a == detected_b,
            "both_detected": detected_a and detected_b,
            "neither_detected": not detected_a and not detected_b,
            "only_model_a": detected_a and not detected_b,
            "only_model_b": detected_b and not detected_a,
            "confidence_diff": abs(conf_a - conf_b),
            "avg_confidence": (conf_a + conf_b) / 2
        }
    
    async def persist_detections(self, results: Dict, comparison: Dict, db_session_factory):
        """Persist detection results to database"""
        try:
            async with db_session_factory() as session:
                for model_name, data in results.items():
                    detection = Detection(
                        event_id=data["event_id"],
                        model_name=model_name,
                        detected=data["detected"],
                        confidence=data["confidence"],
                        threshold=data["threshold"],
                        processing_time_ms=data["processing_time_ms"],
                        picks=json.dumps(data["picks"]),
                        metadata=json.dumps(data["metadata"]),
                        agreement=comparison.get("agreement", False),
                        confidence_diff=comparison.get("confidence_diff", 0.0)
                    )
                    session.add(detection)
                
                await session.commit()
                logger.info(f"Persisted detections for event {data['event_id']}")
                
        except Exception as e:
            logger.error(f"Error persisting to database: {e}")
    
    async def start(self, db_session_factory):
        """Start consuming from Redis"""
        await self.connect()
        self.running = True
        
        # Run both subscriptions concurrently
        await asyncio.gather(
            self.subscribe_waveforms(),
            self.subscribe_detections(db_session_factory)
        )
    
    async def stop(self):
        """Stop consuming"""
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()

# Global consumer instance
consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global consumer
    redis_url = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}"
    consumer = RedisConsumer(redis_url)
    
    # Initialize database
    await init_db()
    
    # Start Redis consumer in background
    from database import async_session
    asyncio.create_task(consumer.start(async_session))
    
    logger.info("Application startup complete")
    yield
    
    # Shutdown
    await consumer.stop()
    logger.info("Application shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Earthquake Detection API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

# REST endpoints
@app.get("/detections", response_model=List[DetectionResponse])
async def get_detections(
    skip: int = 0,
    limit: int = 100,
    model_name: Optional[str] = None,
    detected_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get historical detections"""
    query = select(Detection).order_by(Detection.created_at.desc())
    
    if model_name:
        query = query.where(Detection.model_name == model_name)
    
    if detected_only:
        query = query.where(Detection.detected == True)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    detections = result.scalars().all()
    
    return detections

@app.get("/detections/{event_id}", response_model=List[DetectionResponse])
async def get_detection_by_event(
    event_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detections for a specific event"""
    result = await db.execute(
        select(Detection).where(Detection.event_id == event_id)
    )
    detections = result.scalars().all()
    
    if not detections:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return detections

@app.get("/comparison/stats")
async def get_comparison_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Get comparison statistics"""
    since = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(Detection).where(Detection.created_at >= since)
    )
    detections = result.scalars().all()
    
    # Calculate stats
    total_events = len(set(d.event_id for d in detections))
    agreements = sum(1 for d in detections if d.agreement) // 2  # Divide by 2 since each event has 2 detections
    
    return {
        "period_days": days,
        "total_events": total_events,
        "agreements": agreements,
        "disagreements": total_events - agreements,
        "agreement_rate": agreements / total_events if total_events > 0 else 0
    }

# WebSocket endpoints
@app.websocket("/ws/waveforms")
async def websocket_waveforms(websocket: WebSocket):
    await manager.connect(websocket, "waveforms")
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "waveforms")

@app.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    await manager.connect(websocket, "detections")
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "detections")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)