from sqlalchemy import Column, String, Boolean, Float, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from database import Base

class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(255), nullable=False, index=True)
    model_name = Column(String(100), nullable=False, index=True)
    
    detected = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    processing_time_ms = Column(Float, nullable=False)
    
    picks = Column(Text, nullable=True)  # JSON string
    metadata = Column(Text, nullable=True)  # JSON string
    
    # Comparison fields
    agreement = Column(Boolean, nullable=True, index=True)
    confidence_diff = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_event_model', 'event_id', 'model_name'),
        Index('idx_created_detected', 'created_at', 'detected'),
    )