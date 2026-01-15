import json
import asyncio
import logging
from typing import Dict
import redis.asyncio as aioredis

from config import Config
from models import Detection
from services.comparison import compare_detections

logger = logging.getLogger(__name__)

class RedisConsumer:
    """Consumes messages from Redis pub/sub and processes them"""
    
    def __init__(self, redis_url: str, websocket_manager):
        self.redis_url = redis_url
        self.redis = None
        self.pubsub = None
        self.running = False
        self.detection_cache = {}  # Cache detections by event_id
        self.websocket_manager = websocket_manager
        
    async def connect(self):
        """Connect to Redis"""
        self.redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        self.pubsub = self.redis.pubsub()
        logger.info(f"Connected to Redis at {self.redis_url}")
        
    async def subscribe_waveforms(self):
        """Subscribe to seismic waveform data and broadcast to WebSocket clients"""
        await self.pubsub.subscribe(Config.REDIS_CHANNEL_WAVEFORMS)
        logger.info(f"Subscribed to {Config.REDIS_CHANNEL_WAVEFORMS}")
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
                
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
                    
                    await self.websocket_manager.broadcast(ws_message, "waveforms")
                    
                except Exception as e:
                    logger.error(f"Error processing waveform: {e}")
    
    async def subscribe_detections(self, db_session_factory):
        """Subscribe to detection results from both models and process them"""
        # Subscribe to both model channels
        channels = [
            Config.REDIS_CHANNEL_DETECTIONS_SEISBENCH,
            Config.REDIS_CHANNEL_DETECTIONS_PYTORCH
        ]
        
        await self.pubsub.subscribe(*channels)
        logger.info(f"Subscribed to detection channels: {channels}")
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
                
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
                        comparison = compare_detections(results)
                        
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
                        
                        await self.websocket_manager.broadcast(ws_message, "detections")
                        
                        # Clean up cache
                        del self.detection_cache[event_id]
                        
                        logger.info(f"Processed complete detection for event {event_id}")
                    else:
                        logger.debug(f"Cached partial detection for event {event_id} from {model_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing detection: {e}")
    
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
                        model_metadata=json.dumps(data["metadata"]),
                        agreement=comparison.get("agreement", False),
                        confidence_diff=comparison.get("confidence_diff", 0.0)
                    )
                    session.add(detection)
                
                await session.commit()
                logger.debug(f"Persisted detections for event {data['event_id']}")
                
        except Exception as e:
            logger.error(f"Error persisting to database: {e}")
    
    async def start(self, db_session_factory):
        """Start consuming from Redis"""
        await self.connect()
        self.running = True
        
        logger.info("Starting Redis consumer tasks...")
        
        # Run both subscriptions concurrently
        await asyncio.gather(
            self.subscribe_waveforms(),
            self.subscribe_detections(db_session_factory),
            return_exceptions=True
        )
    
    async def stop(self):
        """Stop consuming"""
        logger.info("Stopping Redis consumer...")
        self.running = False
        
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        if self.redis:
            await self.redis.close()
        
        logger.info("Redis consumer stopped")