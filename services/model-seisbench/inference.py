import logging
import time
import numpy as np

from config import Config

logger = logging.getLogger(__name__)

class InferenceEngine:
    """Handles preprocessing and inference for earthquake detection using SeisBench"""
    
    def __init__(self, model):
        self.model = model
        self.threshold = Config.DETECTION_THRESHOLD
        
    def preprocess_waveform(self, waveform_data, sampling_rate):
        """Preprocess waveform for model input"""
        try:
            # Convert to numpy array
            data = np.array(waveform_data, dtype=np.float32)
            
            # EqTransformer expects 3-component data
            if Config.SIMULATE_3C:
                # Simulate with single component (for testing)
                # In production, fetch all 3 components (E, N, Z)
                data_3c = np.stack([data, data, data], axis=0)
            else:
                # Assume data already has 3 components
                data_3c = data
            
            # Add batch dimension
            data_3c = np.expand_dims(data_3c, axis=0)
            
            return data_3c
            
        except Exception as e:
            logger.error(f"Error preprocessing waveform: {e}")
            return None
    
    def run_inference(self, waveform_data, sampling_rate):
        """Run inference on waveform data"""
        try:
            start_time = time.time()
            
            # Preprocess
            processed_data = self.preprocess_waveform(waveform_data, sampling_rate)
            if processed_data is None:
                return None
            
            # Run model
            annotations = self.model.annotate(processed_data)
            
            # Extract P and S wave picks
            picks = []
            
            # P-wave detection
            p_prob = annotations.select(channel="EQTransformer_P_phase")[0].max()
            if p_prob > self.threshold:
                p_idx = annotations.select(channel="EQTransformer_P_phase")[0].argmax()
                picks.append({
                    "phase": "P",
                    "time": None,  # Would calculate from index and sampling rate
                    "probability": float(p_prob)
                })
            
            # S-wave detection
            s_prob = annotations.select(channel="EQTransformer_S_phase")[0].max()
            if s_prob > self.threshold:
                s_idx = annotations.select(channel="EQTransformer_S_phase")[0].argmax()
                picks.append({
                    "phase": "S",
                    "time": None,
                    "probability": float(s_prob)
                })
            
            # Detection based on either P or S wave
            max_confidence = max(float(p_prob), float(s_prob))
            detected = max_confidence > self.threshold
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "detected": detected,
                "confidence": max_confidence,
                "picks": picks,
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error during inference: {e}")
            return None