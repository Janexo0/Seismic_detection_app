from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from database import get_db
from models import Detection
from schemas import DetectionResponse
from services.comparison import calculate_agreement_rate

router = APIRouter(prefix="/detections", tags=["detections"])

@router.get("", response_model=List[DetectionResponse])
async def get_detections(
    skip: int = 0,
    limit: int = 100,
    detection_model_name: Optional[str] = None,
    detected_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical detections with optional filters
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **detection_model_name**: Filter by model name (e.g., 'seisbench_eqtransformer', 'pytorch_custom')
    - **detected_only**: If true, only return detections where detected=True
    """
    query = select(Detection).order_by(Detection.created_at.desc())
    
    if detection_model_name:
        query = query.where(Detection.detection_model_name == detection_model_name)
    
    if detected_only:
        query = query.where(Detection.detected == True)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    detections = result.scalars().all()
    
    return detections

@router.get("/{event_id}", response_model=List[DetectionResponse])
async def get_detection_by_event(
    event_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all detections for a specific event ID
    
    Returns results from both models for comparison
    """
    result = await db.execute(
        select(Detection).where(Detection.event_id == event_id)
    )
    detections = result.scalars().all()
    
    if not detections:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return detections

@router.get("/stats/comparison")
async def get_comparison_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """
    Get comparison statistics between models
    
    - **days**: Number of days to look back (default: 7)
    
    Returns agreement rate, total events, and breakdown of results
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = await db.execute(
        select(Detection).where(Detection.created_at >= since)
    )
    detections = result.scalars().all()
    
    # Calculate stats
    total_events = len(set(d.event_id for d in detections))
    
    # Count agreements (divide by 2 since each event has 2 detections)
    agreements = sum(1 for d in detections if d.agreement) // 2
    
    # Calculate agreement rate
    agreement_rate = calculate_agreement_rate(detections)
    
    # Count detections by model
    model_stats = {}
    for detection in detections:
        if detection.detection_model_name not in model_stats:
            model_stats[detection.detection_model_name] = {
                "total": 0,
                "detected": 0,
                "not_detected": 0
            }
        model_stats[detection.detection_model_name]["total"] += 1
        if detection.detected:
            model_stats[detection.detection_model_name]["detected"] += 1
        else:
            model_stats[detection.detection_model_name]["not_detected"] += 1
    
    return {
        "period_days": days,
        "total_events": total_events,
        "agreements": agreements,
        "disagreements": total_events - agreements,
        "agreement_rate": agreement_rate,
        "model_stats": model_stats
    }

@router.get("/stats/recent")
async def get_recent_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics for recent detections
    
    - **hours**: Number of hours to look back (default: 24)
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    result = await db.execute(
        select(Detection).where(Detection.created_at >= since)
    )
    detections = result.scalars().all()
    
    total = len(detections)
    detected = sum(1 for d in detections if d.detected)
    
    return {
        "period_hours": hours,
        "total_detections": total,
        "earthquake_detected": detected,
        "no_detection": total - detected,
        "detection_rate": detected / total if total > 0 else 0
    }