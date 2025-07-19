"""
WebSocket management for real-time communication.
"""

from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from datetime import datetime
import structlog

logger = structlog.get_logger()

class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        # Active connections by client ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Room/channel subscriptions
        self.rooms: Dict[str, Set[str]] = {}
        # Client metadata
        self.client_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """Accept and register a new WebSocket connection."""
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.client_metadata[client_id] = {
                "connected_at": datetime.utcnow(),
                "rooms": set()
            }
            logger.info(f"WebSocket client connected: {client_id}")
            
            # Send welcome message
            await self.send_personal_message({
                "type": "connection",
                "status": "connected",
                "client_id": client_id,
                "timestamp": datetime.utcnow().isoformat()
            }, client_id)
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect WebSocket client {client_id}: {e}")
            return False
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            # Remove from all rooms
            for room in self.client_metadata.get(client_id, {}).get("rooms", set()):
                self.leave_room(client_id, room)
            
            # Remove connection
            del self.active_connections[client_id]
            if client_id in self.client_metadata:
                del self.client_metadata[client_id]
            
            logger.info(f"WebSocket client disconnected: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any], exclude_client: Optional[str] = None):
        """Broadcast a message to all connected clients."""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            if client_id != exclude_client:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send broadcast to {client_id}: {e}")
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    def join_room(self, client_id: str, room: str):
        """Add a client to a room/channel."""
        if room not in self.rooms:
            self.rooms[room] = set()
        
        self.rooms[room].add(client_id)
        
        if client_id in self.client_metadata:
            self.client_metadata[client_id]["rooms"].add(room)
        
        logger.info(f"Client {client_id} joined room {room}")
    
    def leave_room(self, client_id: str, room: str):
        """Remove a client from a room/channel."""
        if room in self.rooms and client_id in self.rooms[room]:
            self.rooms[room].remove(client_id)
            
            if not self.rooms[room]:
                del self.rooms[room]
            
            if client_id in self.client_metadata:
                self.client_metadata[client_id]["rooms"].discard(room)
            
            logger.info(f"Client {client_id} left room {room}")
    
    async def broadcast_to_room(self, room: str, message: Dict[str, Any], 
                               exclude_client: Optional[str] = None):
        """Broadcast a message to all clients in a room."""
        if room not in self.rooms:
            return
        
        disconnected_clients = []
        
        for client_id in self.rooms[room]:
            if client_id != exclude_client and client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send room message to {client_id}: {e}")
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    def get_room_members(self, room: str) -> Set[str]:
        """Get all clients in a room."""
        return self.rooms.get(room, set()).copy()
    
    def get_client_rooms(self, client_id: str) -> Set[str]:
        """Get all rooms a client is in."""
        return self.client_metadata.get(client_id, {}).get("rooms", set()).copy()
    
    def is_connected(self, client_id: str) -> bool:
        """Check if a client is connected."""
        return client_id in self.active_connections
    
    def get_connected_clients(self) -> Set[str]:
        """Get all connected client IDs."""
        return set(self.active_connections.keys())
    
    async def handle_message(self, client_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket messages."""
        message_type = message.get("type")
        
        if message_type == "ping":
            # Respond to ping
            await self.send_personal_message({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }, client_id)
        
        elif message_type == "join_room":
            room = message.get("room")
            if room:
                self.join_room(client_id, room)
                await self.send_personal_message({
                    "type": "room_joined",
                    "room": room,
                    "members": list(self.get_room_members(room))
                }, client_id)
                
                # Notify other room members
                await self.broadcast_to_room(room, {
                    "type": "user_joined",
                    "room": room,
                    "client_id": client_id,
                    "timestamp": datetime.utcnow().isoformat()
                }, exclude_client=client_id)
        
        elif message_type == "leave_room":
            room = message.get("room")
            if room:
                self.leave_room(client_id, room)
                await self.send_personal_message({
                    "type": "room_left",
                    "room": room
                }, client_id)
                
                # Notify other room members
                await self.broadcast_to_room(room, {
                    "type": "user_left",
                    "room": room,
                    "client_id": client_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        elif message_type == "room_message":
            room = message.get("room")
            content = message.get("content")
            if room and content:
                await self.broadcast_to_room(room, {
                    "type": "room_message",
                    "room": room,
                    "client_id": client_id,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        elif message_type == "broadcast":
            content = message.get("content")
            if content:
                await self.broadcast({
                    "type": "broadcast",
                    "client_id": client_id,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat()
                }, exclude_client=client_id)

# Global connection manager instance
manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint handler."""
    # Connect client
    connected = await manager.connect(websocket, client_id)
    if not connected:
        return
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Handle message
            await manager.handle_message(client_id, data)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)

async def send_notification(client_id: str, notification: Dict[str, Any]):
    """Send a notification to a specific client."""
    await manager.send_personal_message({
        "type": "notification",
        "data": notification,
        "timestamp": datetime.utcnow().isoformat()
    }, client_id)

async def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all connected clients."""
    await manager.broadcast({
        "type": "event",
        "event_type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    })

async def send_room_event(room: str, event_type: str, data: Dict[str, Any]):
    """Send an event to all clients in a room."""
    await manager.broadcast_to_room(room, {
        "type": "room_event",
        "room": room,
        "event_type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    })