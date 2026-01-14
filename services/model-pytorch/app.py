import os
import json
import time
import signal
import logging
from datetime import datetime

import redis
import torch

from config import Config
from model import CustomEarthquakeModel
from inference import InferenceEngine

logging.basicConfig(level=Config.get_log_level())
logger = logging.getLogger(__name__)

class PyTorchDetector:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            decode_responses=False
        )
        
        self.pubsub = None
        self.model = None
        self.inference_engine = None
        self.device = Config.get_device()
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def load_model(self):
        """Load custom PyTorch model"""
        try:
            logger.info(f"Loading model from {Config.MODEL_PATH}")
            
            # Check if model file exists
            if not os.path.exists(Config.MODEL_PATH):
                logger.warning(f"Model file not found at {Config.MODEL_PATH}, creating dummy model")
                # Create and save a dummy model for testing
                self.model = CustomEarthquakeModel()
                os.makedirs(os.path.dirname(Config.MODEL_PATH), exist_ok=True)
                torch.save(self.model.state_dict(), Config.MODEL_PATH)
            else:
                # Load model
                self.model = CustomEarthquakeModel()
                self.model.load_state_dict(torch.load(Config.MODEL_PATH, map_location=self.device))
            
            self.model.to(self.device)
            self.model.eval()
            
            # Initialize inference engine
            self.inference_engine = InferenceEngine(self.model, self.device)
            
            logger.info(f"Model loaded successfully on {self.device}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def publish_detection(self, event_id, result, station_info):
        """Publish detection result to Redis"""
        try:
            message = {
                "event_id": event_id,
                "model_name": Config.MODEL_NAME,
                "detection_timestamp": datetime.utcnow().isoformat() + "Z",
                "detected": result["detected"],
                "confidence": result["confidence"],
                "threshold": Config.DETECTION_THRESHOLD,
                "processing_time_ms": result["processing_time_ms"],
                "picks": result["picks"],
                "metadata": {
                    "model_version": "pytorch-custom-v1.0",
                    "station": station_info
                }
            }
            
            channel = Config.REDIS_CHANNEL_OUTPUT
            self.redis_client.publish(channel, json.dumps(message))
            
            logger.info(f"Published detection for event {event_id}: detected={result['detected']}, confidence={result['confidence']:.3f}")
            
        except Exception as e:
            logger.error(f"Error publishing detection: {e}")
    
    def process_message(self, message):
        """Process incoming seismic data message"""
        try:
            data = json.loads(message['data'])
            
            event_id = data['event_id']
            waveform_data = data['waveform']['data']
            station_info = data['station']
            
            logger.info(f"Processing event {event_id}")
            
            # Run inference
            result = self.inference_engine.run_inference(waveform_data)
            
            if result:
                self.publish_detection(event_id, result, station_info)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """Main loop - subscribe to Redis and process messages"""
        if not self.load_model():
            logger.error("Cannot start without model")
            return
        
        logger.info(f"Subscribing to {Config.REDIS_CHANNEL_INPUT} channel...")
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(Config.REDIS_CHANNEL_INPUT)
        
        logger.info("Listening for seismic data...")
        
        for message in self.pubsub.listen():
            if not self.running:
                break
            
            if message['type'] == 'message':
                self.process_message(message)
        
        logger.info("PyTorch detector stopped")
        self.pubsub.close()

def main():
    detector = PyTorchDetector()
    
    # Wait for Redis
    max_retries = Config.HEALTH_CHECK_RETRIES
    for i in range(max_retries):
        try:
            detector.redis_client.ping()
            logger.info("Redis connection healthy")
            break
        except:
            logger.info(f"Waiting for Redis... ({i+1}/{max_retries})")
            time.sleep(Config.HEALTH_CHECK_INTERVAL)
    else:
        logger.error("Failed to connect to Redis")
        return
    
    detector.run()

if __name__ == "__main__":
    main()