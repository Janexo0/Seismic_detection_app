import json
import time
import signal
import logging
from datetime import datetime
from typing import Optional
import uuid

import redis
from obspy import UTCDateTime
from obspy.clients.fdsn import Client

from config import Config

logging.basicConfig(level=Config.get_log_level())
logger = logging.getLogger(__name__)

class SeismicIngestor:
    def __init__(self):
        # Validate configuration
        Config.validate()
        
        self.redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            decode_responses=False
        )
        
        self.running = True
        self.fdsn_client = None
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def connect_fdsn(self):
        """Initialize FDSN client"""
        try:
            self.fdsn_client = Client(Config.FDSN_CLIENT, timeout=Config.FDSN_TIMEOUT)
            logger.info(f"Connected to FDSN client: {Config.FDSN_CLIENT}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to FDSN: {e}")
            return False
    
    def fetch_waveform_window(self, start_time: UTCDateTime, end_time: UTCDateTime):
        """Fetch a single waveform window"""
        try:
            stream = self.fdsn_client.get_waveforms(
                network=Config.NETWORK,
                station=Config.STATION,
                location=Config.LOCATION,
                channel=Config.CHANNEL,
                starttime=start_time,
                endtime=end_time
            )
            
            if len(stream) == 0:
                logger.warning("No data returned from FDSN")
                return None
                
            # Merge traces and detrend
            stream.merge(fill_value='interpolate')
            stream.detrend('linear')
            
            return stream[0]
            
        except Exception as e:
            logger.error(f"Error fetching waveform: {e}")
            return None
    
    def publish_seismic_data(self, trace):
        """Publish seismic data to Redis"""
        try:
            event_id = str(uuid.uuid4())
            
            # Prepare message according to schema
            message = {
                "event_id": event_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "station": {
                    "network": trace.stats.network,
                    "station": trace.stats.station,
                    "location": trace.stats.location,
                    "channel": trace.stats.channel
                },
                "sampling_rate": float(trace.stats.sampling_rate),
                "window_start": trace.stats.starttime.isoformat() + "Z",
                "window_end": trace.stats.endtime.isoformat() + "Z",
                "waveform": {
                    "data": trace.data.tolist(),
                    "length": len(trace.data),
                    "encoding": "float32",
                    "unit": "m/s"
                },
                "metadata": {
                    "latitude": getattr(trace.stats, 'latitude', None),
                    "longitude": getattr(trace.stats, 'longitude', None),
                    "elevation": getattr(trace.stats, 'elevation', None)
                }
            }
            
            # Publish to Redis channel
            channel = Config.REDIS_CHANNEL_OUTPUT
            self.redis_client.publish(channel, json.dumps(message))
            
            logger.info(f"Published event {event_id} to {channel}")
            return event_id
            
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
            return None
    
    def run_realtime(self):
        """Run in near-realtime mode, fetching recent data"""
        if not self.connect_fdsn():
            logger.error("Cannot start without FDSN connection")
            return
        
        logger.info("Starting real-time ingestion...")
        logger.info(f"Station: {Config.NETWORK}.{Config.STATION}.{Config.LOCATION}.{Config.CHANNEL}")
        logger.info(f"Window: {Config.WINDOW_DURATION}s with {Config.OVERLAP}s overlap")
        
        last_end_time = UTCDateTime() - Config.WINDOW_DURATION
        
        while self.running:
            try:
                # Calculate next window
                start_time = last_end_time - Config.OVERLAP
                end_time = start_time + Config.WINDOW_DURATION
                
                # Don't fetch future data
                now = UTCDateTime()
                if end_time > now:
                    sleep_seconds = (end_time - now) + Config.DATA_AVAILABILITY_DELAY
                    logger.info(f"Waiting {sleep_seconds:.1f}s for data availability...")
                    time.sleep(sleep_seconds)
                    continue
                
                logger.info(f"Fetching: {start_time} to {end_time}")
                
                trace = self.fetch_waveform_window(start_time, end_time)
                
                if trace:
                    self.publish_seismic_data(trace)
                    last_end_time = end_time
                else:
                    logger.warning("No trace data, retrying...")
                    time.sleep(Config.RETRY_DELAY)
                    continue
                
                # Small delay between windows
                time.sleep(Config.WINDOW_DELAY)
                
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(Config.ERROR_DELAY)
        
        logger.info("Ingestor stopped")
    
    def health_check(self):
        """Check service health"""
        try:
            self.redis_client.ping()
            return True
        except:
            return False

def main():
    ingestor = SeismicIngestor()
    
    # Wait for Redis to be ready
    max_retries = Config.HEALTH_CHECK_RETRIES
    for i in range(max_retries):
        if ingestor.health_check():
            logger.info("Redis connection healthy")
            break
        logger.info(f"Waiting for Redis... ({i+1}/{max_retries})")
        time.sleep(Config.HEALTH_CHECK_INTERVAL)
    else:
        logger.error("Failed to connect to Redis")
        return
    
    ingestor.run_realtime()

if __name__ == "__main__":
    main()