import logging
import time
import numpy as np
import torch

from config import Config

logger = logging.getLogger(__name__)

class InferenceEngine:
    """Handles preprocessing and inference for earthquake detection"""
    
    def __init__(self, model, device):
        self.model = model
        self.device = device
        self.threshold = Config.DETECTION_THRESHOLD
        
    def preprocess_waveform(self, waveform_data):
        """Preprocess waveform for model input"""
        try:
            # Convert to numpy array and normalize
            data = np.array(waveform_data, dtype=np.float32)
            
            # Normalize
            data = (data - np.mean(data)) / (np.std(data) + 1e-8)
            
            # Reshape for model input: (batch, channels, length)
            data = data.reshape(1, 1, -1)
            
            # Convert to tensor
            tensor = torch.from_numpy(data).to(self.device)
            
            return tensor
            
        except Exception as e:
            logger.error(f"Error preprocessing waveform: {e}")
            return None
    
    def run_inference(self, waveform_data):
        """Run inference on waveform data"""
        try:
            start_time = time.time()
            
            # Preprocess
            input_tensor = self.preprocess_waveform(waveform_data)
            if input_tensor is None:
                return None
            
            # Run model
            with torch.no_grad():
                output = self.model(input_tensor)
            
            # Extract probabilities
            probs = output.cpu().numpy()[0]
            p_prob = float(probs[0])
            s_prob = float(probs[1])
            noise_prob = float(probs[2])
            
            # Create picks
            picks = []
            if p_prob > self.threshold:
                picks.append({
                    "phase": "P",
                    "time": None,
                    "probability": p_prob
                })
            
            if s_prob > self.threshold:
                picks.append({
                    "phase": "S",
                    "time": None,
                    "probability": s_prob
                })
            
            # Detection based on max probability
            max_signal_prob = max(p_prob, s_prob)
            detected = max_signal_prob > self.threshold
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "detected": detected,
                "confidence": max_signal_prob,
                "picks": picks,
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error during inference: {e}")
            return None