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
    """Consumes messages from Redis pub/sub and processes them using a single listener loop"""
    
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

    async def start(self, db_session_factory):
        """Start consuming from Redis with a unified dispatcher loop"""
        await self.connect()
        self.running = True
        
        # Subskrybujemy wszystkie kanały na jednym obiekcie pubsub
        channels = [
            Config.REDIS_CHANNEL_WAVEFORMS,
            Config.REDIS_CHANNEL_DETECTIONS_SEISBENCH,
            Config.REDIS_CHANNEL_DETECTIONS_PYTORCH
        ]
        await self.pubsub.subscribe(*channels)
        logger.info(f"Subscribed to all channels: {channels}")

        try:
            # JEDYNA pętla nasłuchująca w całej aplikacji API
            async for message in self.pubsub.listen():
                if not self.running:
                    break
                
                if message["type"] == "message":
                    channel = message["channel"]
                    raw_data = message["data"]
                    
                    # DISPATCHER: Kierowanie wiadomości do odpowiedniej funkcji
                    if channel == Config.REDIS_CHANNEL_WAVEFORMS:
                        await self._handle_waveform(raw_data)
                    else:
                        await self._handle_detection(raw_data, db_session_factory)
                        
        except Exception as e:
            logger.error(f"Critical error in Redis listener loop: {e}")
        finally:
            await self.stop()

    async def _handle_waveform(self, raw_data):
        """Process and broadcast waveform data"""
        try:
            data = json.loads(raw_data)
            ws_message = {
                "type": "waveform",
                "event_id": data["event_id"],
                "timestamp": data["timestamp"],
                "station": data["station"],
                "data": data["waveform"]["data"][:1000],  # Limit dla wydajności frontendu
                "sampling_rate": data["sampling_rate"]
            }
            await self.websocket_manager.broadcast(ws_message, "waveforms")
        except Exception as e:
            logger.error(f"Error processing waveform data: {e}")

    async def _handle_detection(self, raw_data, db_session_factory):
        """Process, compare, and broadcast detection results"""
        try:
            data = json.loads(raw_data)
            event_id = data["event_id"]
            model_name = data["detection_model_name"]

            # Cache'owanie wyników
            if event_id not in self.detection_cache:
                self.detection_cache[event_id] = {}
            
            self.detection_cache[event_id][model_name] = data

            # Jeśli mamy komplet (2 modele), przetwarzamy porównanie
            if len(self.detection_cache[event_id]) >= 2:
                results = self.detection_cache[event_id]
                comparison = compare_detections(results)
                
                # Zapis do bazy (asynchronicznie)
                await self.persist_detections(results, comparison, db_session_factory)
                
                # Wysyłka do frontendu
                ws_message = {
                    "type": "detection",
                    "event_id": event_id,
                    "timestamp": data["detection_timestamp"],
                    "models": results,
                    "comparison": comparison
                }
                await self.websocket_manager.broadcast(ws_message, "detections")
                
                # Czyszczenie pamięci podręcznej
                del self.detection_cache[event_id]
                logger.info(f"Broadcasted complete detection for event {event_id}")
                
        except Exception as e:
            logger.error(f"Error processing detection result: {e}")

    async def persist_detections(self, results: Dict, comparison: Dict, db_session_factory):
        """Persist detection results to database"""
        try:
            async with db_session_factory() as session:
                for detection_model_name, data in results.items():
                    detection = Detection(
                        event_id=data["event_id"],
                        detection_model_name=detection_model_name,
                        detected=data["detected"],
                        confidence=data["confidence"],
                        threshold=data["threshold"],
                        processing_time_ms=data["processing_time_ms"],
                        picks=json.dumps(data["picks"]),
                        detection_model_metadata=json.dumps(data["detection_model_metadata"]),
                        agreement=comparison.get("agreement", False),
                        confidence_diff=comparison.get("confidence_diff", 0.0)
                    )
                    session.add(detection)
                
                await session.commit()
        except Exception as e:
            logger.error(f"Database persistence error: {e}")

    async def stop(self):
        """Graceful shutdown"""
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
        logger.info("Redis consumer stopped")