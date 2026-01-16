from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional
import uuid

class DetectionBase(BaseModel):
    event_id: str
    detection_model_name: str
    detected: bool
    confidence: float
    threshold: float
    processing_time_ms: float
    picks: Optional[str] = None
    detection_model_metadata: Optional[str] = Field(None, description="Model-specific metadata as JSON string")

class DetectionCreate(DetectionBase):
    pass

class DetectionResponse(DetectionBase):
    id: uuid.UUID
    agreement: Optional[bool] = None
    confidence_diff: Optional[float] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ComparisonResult(BaseModel):
    agreement: bool
    both_detected: bool
    neither_detected: bool
    only_model_a: bool
    only_model_b: bool
    confidence_diff: float
    avg_confidence: float