import os
import logging

class Config:
    # Service
    SERVICE_NAME = os.getenv('SERVICE_NAME', 'ingestor')
    
    # Redis Connection
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Redis Channels
    REDIS_CHANNEL_OUTPUT = os.getenv('REDIS_CHANNEL_OUTPUT', 'seismic:waveforms')
    
    # FDSN Configuration
    FDSN_CLIENT = os.getenv('FDSN_CLIENT', 'IRIS')
    FDSN_TIMEOUT = int(os.getenv('FDSN_TIMEOUT', 30))
    
    # Station Configuration
    NETWORK = os.getenv('NETWORK', 'IU')
    STATION = os.getenv('STATION', 'ANMO')
    LOCATION = os.getenv('LOCATION', '00')
    CHANNEL = os.getenv('CHANNEL', 'BHZ')
    
    # Window Configuration
    WINDOW_DURATION = int(os.getenv('WINDOW_DURATION', 60))  # seconds
    OVERLAP = int(os.getenv('OVERLAP', 10))  # seconds
    
    # Timing
    DATA_AVAILABILITY_DELAY = int(os.getenv('DATA_AVAILABILITY_DELAY', 5))  # seconds to wait for data
    WINDOW_DELAY = int(os.getenv('WINDOW_DELAY', 2))  # seconds between windows
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', 5))  # seconds before retry
    ERROR_DELAY = int(os.getenv('ERROR_DELAY', 10))  # seconds after error
    
    # Health Check
    HEALTH_CHECK_RETRIES = int(os.getenv('HEALTH_CHECK_RETRIES', 30))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 2))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        assert cls.WINDOW_DURATION > 0, "WINDOW_DURATION must be positive"
        assert cls.OVERLAP >= 0, "OVERLAP must be non-negative"
        assert cls.OVERLAP < cls.WINDOW_DURATION, "OVERLAP must be less than WINDOW_DURATION"
    
    @classmethod
    def get_log_level(cls):
        """Convert log level string to logging constant"""
        return getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)