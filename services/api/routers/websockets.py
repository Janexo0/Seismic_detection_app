import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

websocket_manager = None

def init_websocket_router(manager):
    """Initialize the router with the websocket manager"""
    global websocket_manager
    websocket_manager = manager

router = APIRouter(tags=["websockets"])

@router.websocket("/ws/waveforms")
async def websocket_waveforms(websocket: WebSocket):
    """
    WebSocket endpoint for real-time waveform data
    
    Clients connect here to receive seismic waveform updates
    """
    await websocket_manager.connect(websocket, "waveforms")
    try:
        while True:
            # Keep connection alive
            # Client can send ping messages if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, "waveforms")
    except Exception as e:
        logger.error(f"WebSocket error (waveforms): {e}")
        websocket_manager.disconnect(websocket, "waveforms")

@router.websocket("/ws/detections")
async def websocket_detections(websocket: WebSocket):
    """
    WebSocket endpoint for real-time detection results
    
    Clients connect here to receive earthquake detection updates
    from both models with comparison results
    """
    await websocket_manager.connect(websocket, "detections")
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, "detections")
    except Exception as e:
        logger.error(f"WebSocket error (detections): {e}")
        websocket_manager.disconnect(websocket, "detections")

@router.get("/ws/status")
async def websocket_status():
    """Get current WebSocket connection statistics"""
    return {
        "connections": websocket_manager.get_all_connection_counts(),
        "channels": list(websocket_manager.active_connections.keys())
    }