import logging
import time
import numpy as np
from obspy import Stream, Trace

from config import Config

logger = logging.getLogger(__name__)

class InferenceEngine:
    """Handles preprocessing and inference for earthquake detection using SeisBench"""
    
    def __init__(self, model):
        self.model = model
        self.threshold = Config.DETECTION_THRESHOLD
        
    def preprocess_waveform(self, waveform_data, sampling_rate):
        """Preprocess waveform for model input - convert to ObsPy Stream"""
        try:
            # Convert to numpy array
            data = np.array(waveform_data, dtype=np.float32)
            
            # Create ObsPy Stream with 3 components
            # EQTransformer expects 3-component data (E, N, Z)
            stream = Stream()
            
            if Config.SIMULATE_3C:
                # Simulate 3 components from single channel (for testing)
                # In production, you would fetch actual E, N, Z components
                for i, channel in enumerate(['HHE', 'HHN', 'HHZ']):
                    trace = Trace(data=data.copy())
                    trace.stats.sampling_rate = sampling_rate
                    trace.stats.channel = channel
                    stream.append(trace)
            else:
                # Single component - still need to create stream
                trace = Trace(data=data)
                trace.stats.sampling_rate = sampling_rate
                stream.append(trace)
            
            return stream
            
        except Exception as e:
            logger.error(f"Error preprocessing waveform: {e}")
            return None
    
    def run_inference(self, waveform_data, sampling_rate):
        """Run inference on waveform data"""
        try:
            start_time = time.time()
            
            # Preprocess - returns ObsPy Stream
            stream = self.preprocess_waveform(waveform_data, sampling_rate)
            if stream is None:
                return None
            
            # Run model - SeisBench models work with ObsPy Streams
            annotations = self.model.annotate(stream)
            
            # Extract P and S wave picks
            picks = []
            
            # Try to get P-wave detection
            try:
                p_channel = annotations.select(channel="*_P*")
                if len(p_channel) > 0:
                    p_prob = float(p_channel[0].max())
                    if p_prob > self.threshold:
                        p_idx = int(p_channel[0].argmax())
                        picks.append({
                            "phase": "P",
                            "time": None,  # Would calculate from index and sampling rate
                            "probability": p_prob
                        })
                else:
                    p_prob = 0.0
            except Exception as e:
                logger.warning(f"Could not extract P-wave: {e}")
                p_prob = 0.0
            
            # Try to get S-wave detection
            try:
                s_channel = annotations.select(channel="*_S*")
                if len(s_channel) > 0:
                    s_prob = float(s_channel[0].max())
                    if s_prob > self.threshold:
                        s_idx = int(s_channel[0].argmax())
                        picks.append({
                            "phase": "S",
                            "time": None,
                            "probability": s_prob
                        })
                else:
                    s_prob = 0.0
            except Exception as e:
                logger.warning(f"Could not extract S-wave: {e}")
                s_prob = 0.0
            
            # Detection based on either P or S wave
            max_confidence = max(p_prob, s_prob)
            detected = max_confidence > self.threshold
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "detected": detected,
                "confidence": max_confidence,
                "picks": picks,
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error during inference: {e}", exc_info=True)
            return None