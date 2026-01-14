import os
import logging

class Config:
    # Service
    SERVICE_NAME = os.getenv('SERVICE_NAME', 'model-seisbench')
    
    # Redis Connection
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Redis Channels
    REDIS_CHANNEL_INPUT = os.getenv('REDIS_CHANNEL_INPUT', 'seismic:waveforms')
    REDIS_CHANNEL_OUTPUT = os.getenv('REDIS_CHANNEL_OUTPUT', 'seismic:detections:seisbench')
    
    # Model Configuration
    MODEL_NAME = os.getenv('MODEL_NAME', 'seisbench_eqtransformer')
    SEISBENCH_MODEL = os.getenv('SEISBENCH_MODEL', 'EQTransformer')  # EQTransformer, PhaseNet, GPD
    SEISBENCH_MODEL_VERSION = os.getenv('SEISBENCH_MODEL_VERSION', 'original')
    DETECTION_THRESHOLD = float(os.getenv('DETECTION_THRESHOLD', 0.5))
    
    # Processing
    SIMULATE_3C = os.getenv('SIMULATE_3C', 'true').lower() == 'true'  # Simulate 3-component data
    
    # Health Check
    HEALTH_CHECK_RETRIES = int(os.getenv('HEALTH_CHECK_RETRIES', 30))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 2))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_log_level(cls):
        """Convert log level string to logging constant"""
        return getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)