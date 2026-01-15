import logging
from typing import Dict

logger = logging.getLogger(__name__)

def compare_detections(results: Dict) -> Dict:
    """
    Compare detection results from multiple models
    
    Args:
        results: Dictionary with model names as keys and detection results as values
        
    Returns:
        Dictionary with comparison metrics
    """
    models = list(results.keys())
    
    if len(models) != 2:
        logger.warning(f"Expected 2 models for comparison, got {len(models)}")
        return {
            "agreement": False,
            "both_detected": False,
            "neither_detected": False,
            "only_model_a": False,
            "only_model_b": False,
            "confidence_diff": 0.0,
            "avg_confidence": 0.0
        }
    
    model_a, model_b = models[0], models[1]
    
    detected_a = results[model_a]["detected"]
    detected_b = results[model_b]["detected"]
    conf_a = results[model_a]["confidence"]
    conf_b = results[model_b]["confidence"]
    
    comparison = {
        "agreement": detected_a == detected_b,
        "both_detected": detected_a and detected_b,
        "neither_detected": not detected_a and not detected_b,
        "only_model_a": detected_a and not detected_b,
        "only_model_b": detected_b and not detected_a,
        "confidence_diff": abs(conf_a - conf_b),
        "avg_confidence": (conf_a + conf_b) / 2
    }
    
    logger.debug(f"Comparison: {model_a} vs {model_b} - Agreement: {comparison['agreement']}")
    
    return comparison

def calculate_agreement_rate(detections: list) -> float:
    """
    Calculate agreement rate from a list of detections
    
    Args:
        detections: List of Detection objects
        
    Returns:
        Agreement rate as a float between 0 and 1
    """
    if not detections:
        return 0.0
    
    # Group by event_id
    events = {}
    for detection in detections:
        if detection.event_id not in events:
            events[detection.event_id] = []
        events[detection.event_id].append(detection)
    
    # Count agreements
    agreements = sum(
        1 for event_detections in events.values()
        if len(event_detections) >= 2 and event_detections[0].agreement
    )
    
    total_events = len(events)
    
    return agreements / total_events if total_events > 0 else 0.0