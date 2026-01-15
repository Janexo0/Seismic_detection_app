import os
import logging

class Config:
    # Service
    SERVICE_NAME = os.getenv('SERVICE_NAME', 'api')
    API_VERSION = os.getenv('API_VERSION', '1.0.0')
    
    # Server
    HOST = os.getenv('API_HOST', '0.0.0.0')
    PORT = int(os.getenv('API_PORT', 8000))
    WORKERS = int(os.getenv('API_WORKERS', 4))
    
    # Database
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'earthquake_db')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'earthquake_user')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'earthquake_pass')
    
    @classmethod
    def get_database_url(cls):
        return f"postgresql+asyncpg://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    @classmethod
    def get_redis_url(cls):
        return f"redis://{cls.REDIS_HOST}:{cls.REDIS_PORT}"
    
    # Redis Channels
    REDIS_CHANNEL_WAVEFORMS = os.getenv('REDIS_CHANNEL_WAVEFORMS', 'seismic:waveforms')
    REDIS_CHANNEL_DETECTIONS_SEISBENCH = os.getenv('REDIS_CHANNEL_DETECTIONS_SEISBENCH', 'seismic:detections:seisbench')
    REDIS_CHANNEL_DETECTIONS_PYTORCH = os.getenv('REDIS_CHANNEL_DETECTIONS_PYTORCH', 'seismic:detections:pytorch')
    REDIS_CHANNEL_ALERTS = os.getenv('REDIS_CHANNEL_ALERTS', 'seismic:alerts')
    
    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')
    
    # Detection comparison
    TIME_WINDOW_MATCH = float(os.getenv('TIME_WINDOW_MATCH', 5.0))
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', 0.3))
    
    # Cache settings
    DETECTION_CACHE_TTL = int(os.getenv('DETECTION_CACHE_TTL', 300))  # 5 minutes
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_log_level(cls):
        """Convert log level string to logging constant"""
        return getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)