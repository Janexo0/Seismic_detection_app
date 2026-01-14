import os
import logging
import torch

class Config:
    # Service
    SERVICE_NAME = os.getenv('SERVICE_NAME', 'model-pytorch')
    
    # Redis Connection
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Redis Channels
    REDIS_CHANNEL_INPUT = os.getenv('REDIS_CHANNEL_INPUT', 'seismic:waveforms')
    REDIS_CHANNEL_OUTPUT = os.getenv('REDIS_CHANNEL_OUTPUT', 'seismic:detections:pytorch')
    
    # Model Configuration
    MODEL_NAME = os.getenv('MODEL_NAME', 'pytorch_custom')
    MODEL_PATH = os.getenv('MODEL_PATH', '/models/custom_model.pt')
    DETECTION_THRESHOLD = float(os.getenv('DETECTION_THRESHOLD', 0.5))
    
    # Processing
    GPU_ENABLED = os.getenv('GPU_ENABLED', 'auto')  # 'auto', 'true', 'false'
    
    # Health Check
    HEALTH_CHECK_RETRIES = int(os.getenv('HEALTH_CHECK_RETRIES', 30))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 2))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_device(cls):
        """Get torch device based on configuration"""
        if cls.GPU_ENABLED == 'auto':
            return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        elif cls.GPU_ENABLED.lower() == 'true':
            return torch.device('cuda')
        else:
            return torch.device('cpu')
    
    @classmethod
    def get_log_level(cls):
        """Convert log level string to logging constant"""
        return getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)