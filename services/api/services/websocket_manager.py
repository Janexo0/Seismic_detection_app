import logging
from typing import List, Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for different channels"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "waveforms": [],
            "detections": []
        }

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[channel].append(websocket)
        logger.info(f"Client connected to {channel} channel. Total: {len(self.active_connections[channel])}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
            logger.info(f"Client disconnected from {channel} channel. Total: {len(self.active_connections[channel])}")

    async def broadcast(self, message: dict, channel: str):
        """Broadcast message to all connected clients on a channel"""
        if not self.active_connections[channel]:
            return
        
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            if conn in self.active_connections[channel]:
                self.active_connections[channel].remove(conn)
        
        if disconnected:
            logger.info(f"Cleaned up {len(disconnected)} disconnected clients from {channel}")
    
    def get_connection_count(self, channel: str) -> int:
        """Get the number of active connections for a channel"""
        return len(self.active_connections[channel])
    
    def get_all_connection_counts(self) -> Dict[str, int]:
        """Get connection counts for all channels"""
        return {
            channel: len(connections) 
            for channel, connections in self.active_connections.items()
        }