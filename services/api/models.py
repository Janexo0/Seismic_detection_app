from sqlalchemy import Column, Boolean, Float, DateTime, Text, Index, func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from database import Base

class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    created_at = Column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc), server_default=func.now(),nullable=False, index=True)

    event_id = Column(Text, nullable=False, index=True)
    detection_model_name = Column(Text, nullable=False, index=True)
    
    detected = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    processing_time_ms = Column(Float, nullable=False)
    
    picks = Column(Text, nullable=True)  # JSON string
    detection_model_metadata = Column(Text, nullable=True)  # JSON string 
    
    # Comparison fields
    agreement = Column(Boolean, nullable=True, index=True)
    confidence_diff = Column(Float, nullable=True)
        
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_event_model', 'event_id', 'detection_model_name'),
        Index('idx_created_detected', 'created_at', 'detected'),
    )