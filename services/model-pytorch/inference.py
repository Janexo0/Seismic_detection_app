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
            
            # Model expects 3 channels - simulate from single channel
            # In production, you might have actual 3-component data
            data_3c = np.stack([data, data, data], axis=0)
            
            # Add batch dimension: (batch, channels, length)
            data_3c = np.expand_dims(data_3c, axis=0)
            
            # Convert to tensor
            tensor = torch.from_numpy(data_3c).to(self.device)
            
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
            
            # Run model - returns probability [0, 1]
            with torch.no_grad():
                output = self.model(input_tensor)
            
            # Extract probability (binary classification)
            probability = float(output.cpu().numpy()[0, 0])
            
            # Detection based on threshold
            detected = probability > self.threshold
            
            # Create picks (empty for binary model, but kept for consistency)
            picks = []
            if detected:
                picks.append({
                    "phase": "Event",
                    "time": None,
                    "probability": probability
                })
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "detected": detected,
                "confidence": probability,
                "picks": picks,
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error during inference: {e}")
            return None