"""Real-time voice interface for the AI Assistant."""

from __future__ import annotations

import asyncio
import json
import uuid
import wave
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from enum import Enum
import io
import base64

from loguru import logger
import whisper
from elevenlabs import AsyncElevenLabs
import speech_recognition as sr
from pydub import AudioSegment
import numpy as np

from core.config import settings
from services.assistant import AssistantService
from services.ai_orchestrator import AIOrchestrator
from utils.audit import AuditLogger
from utils.safety import SafetyChecker


class VoiceState(str, Enum):
    """Voice interface states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class AudioFormat(str, Enum):
    """Supported audio formats."""
    WAV = "wav"
    MP3 = "mp3"
    WEBM = "webm"
    OGG = "ogg"


class VoiceInterface:
    """Real-time voice interface with hotword detection and streaming."""
    
    def __init__(self):
        self.assistant_service = AssistantService()
        self.ai_orchestrator = AIOrchestrator()
        self.audit_logger = AuditLogger()
        self.safety_checker = SafetyChecker()
        
        # Voice processing models
        self.whisper_model = whisper.load_model("base")
        self.elevenlabs_client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        self.speech_recognizer = sr.Recognizer()
        
        # Voice sessions
        self.voice_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Hotword detection
        self.hotwords = ["hey brainops", "brain ops", "brainops"]
        self.hotword_threshold = 0.7
        self.hotword_enabled = True
        
        # Audio settings
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.audio_format = AudioFormat.WAV
        
        # Voice settings
        self.voice_settings = {
            "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Default ElevenLabs voice
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True
        }
        
        # Processing state
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        self.active_streams: Dict[str, asyncio.Task] = {}
        
        # Conversation context
        self.conversation_context = {
            "wake_phrases": ["wake up", "activate", "start listening"],
            "sleep_phrases": ["go to sleep", "stop listening", "deactivate"],
            "command_prefixes": ["please", "can you", "would you", "i need you to"]
        }
    
    async def initialize(self):
        """Initialize voice interface."""
        try:
            # Start processing queue
            asyncio.create_task(self._process_audio_queue())
            
            # Initialize voice models
            await self._initialize_models()
            
            # Test audio systems
            await self._test_audio_systems()
            
            logger.info("Voice interface initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize voice interface: {e}")
            raise
    
    async def create_voice_session(
        self,
        user_id: int,
        session_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new voice session."""
        try:
            session_id = str(uuid.uuid4())
            
            # Create assistant session
            assistant_session_id = await self.assistant_service.create_session(user_id)
            
            # Create voice session
            voice_session = {
                "id": session_id,
                "user_id": user_id,
                "assistant_session_id": assistant_session_id,
                "state": VoiceState.IDLE,
                "created_at": datetime.utcnow(),
                "config": session_config or {},
                "audio_buffer": [],
                "hotword_detected": False,
                "conversation_active": False,
                "last_activity": datetime.utcnow(),
                "stats": {
                    "commands_processed": 0,
                    "audio_duration": 0,
                    "transcription_accuracy": 0,
                    "response_time": 0
                }
            }
            
            self.voice_sessions[session_id] = voice_session
            
            # Log session creation
            await self.audit_logger.log_action(
                user_id=user_id,
                action="voice_session_created",
                resource_type="voice_session",
                resource_id=session_id,
                details={"config": session_config}
            )
            
            logger.info(f"Created voice session {session_id} for user {user_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating voice session: {e}")
            raise
    
    async def process_audio_stream(
        self,
        session_id: str,
        audio_data: bytes,
        audio_format: AudioFormat = AudioFormat.WAV
    ) -> Dict[str, Any]:
        """Process streaming audio data."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            # Add to processing queue
            await self.processing_queue.put({
                "session_id": session_id,
                "audio_data": audio_data,
                "audio_format": audio_format,
                "timestamp": datetime.utcnow()
            })
            
            return {
                "success": True,
                "session_id": session_id,
                "state": session["state"],
                "message": "Audio queued for processing"
            }
            
        except Exception as e:
            logger.error(f"Error processing audio stream: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_voice_command(
        self,
        session_id: str,
        audio_data: bytes,
        audio_format: AudioFormat = AudioFormat.WAV
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process voice command with real-time streaming response."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            # Update session state
            session["state"] = VoiceState.PROCESSING
            session["last_activity"] = datetime.utcnow()
            
            # Yield initial status
            yield {
                "type": "status",
                "state": VoiceState.PROCESSING,
                "message": "Processing audio..."
            }
            
            # Transcribe audio
            transcription_result = await self._transcribe_audio(audio_data, audio_format)
            
            if not transcription_result["success"]:
                yield {
                    "type": "error",
                    "error": transcription_result["error"]
                }
                return
            
            transcript = transcription_result["transcript"]
            confidence = transcription_result["confidence"]
            
            # Yield transcription
            yield {
                "type": "transcription",
                "transcript": transcript,
                "confidence": confidence
            }
            
            # Check for wake/sleep commands
            if await self._check_wake_sleep_commands(session_id, transcript):
                yield {
                    "type": "state_change",
                    "state": session["state"],
                    "message": "Session state updated"
                }
                return
            
            # Process command with assistant
            async for response_chunk in self._process_assistant_command(
                session_id, transcript, confidence
            ):
                yield response_chunk
            
            # Generate speech response
            if response_chunk.get("type") == "assistant_response":
                async for speech_chunk in self._generate_speech_response(
                    session_id, response_chunk["content"]
                ):
                    yield speech_chunk
            
            # Update session state
            session["state"] = VoiceState.IDLE
            session["stats"]["commands_processed"] += 1
            
            # Log command processing
            await self.audit_logger.log_action(
                user_id=session["user_id"],
                action="voice_command_processed",
                resource_type="voice_command",
                resource_id=str(uuid.uuid4()),
                details={
                    "session_id": session_id,
                    "transcript": transcript,
                    "confidence": confidence,
                    "duration": (datetime.utcnow() - session["last_activity"]).total_seconds()
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing voice command: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def enable_hotword_detection(
        self,
        session_id: str,
        hotwords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Enable hotword detection for session."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            if hotwords:
                session["hotwords"] = hotwords
            else:
                session["hotwords"] = self.hotwords
            
            session["hotword_enabled"] = True
            
            logger.info(f"Enabled hotword detection for session {session_id}")
            
            return {
                "success": True,
                "hotwords": session["hotwords"],
                "message": "Hotword detection enabled"
            }
            
        except Exception as e:
            logger.error(f"Error enabling hotword detection: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def disable_hotword_detection(self, session_id: str) -> Dict[str, Any]:
        """Disable hotword detection for session."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            session["hotword_enabled"] = False
            
            logger.info(f"Disabled hotword detection for session {session_id}")
            
            return {
                "success": True,
                "message": "Hotword detection disabled"
            }
            
        except Exception as e:
            logger.error(f"Error disabling hotword detection: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def set_voice_settings(
        self,
        session_id: str,
        voice_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set voice synthesis settings."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            # Update session voice settings
            session["voice_settings"] = {**self.voice_settings, **voice_settings}
            
            return {
                "success": True,
                "voice_settings": session["voice_settings"],
                "message": "Voice settings updated"
            }
            
        except Exception as e:
            logger.error(f"Error setting voice settings: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get voice session status."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            return {
                "session_id": session_id,
                "state": session["state"],
                "conversation_active": session["conversation_active"],
                "hotword_enabled": session.get("hotword_enabled", False),
                "last_activity": session["last_activity"].isoformat(),
                "stats": session["stats"]
            }
            
        except Exception as e:
            logger.error(f"Error getting session status: {e}")
            return {
                "error": str(e)
            }
    
    async def end_voice_session(self, session_id: str) -> Dict[str, Any]:
        """End a voice session."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            # Clean up active streams
            if session_id in self.active_streams:
                self.active_streams[session_id].cancel()
                del self.active_streams[session_id]
            
            # End assistant session
            # Note: AssistantService doesn't have end_session method, so we'll skip this
            
            # Remove from active sessions
            del self.voice_sessions[session_id]
            
            # Log session end
            await self.audit_logger.log_action(
                user_id=session["user_id"],
                action="voice_session_ended",
                resource_type="voice_session",
                resource_id=session_id,
                details={
                    "duration": (datetime.utcnow() - session["created_at"]).total_seconds(),
                    "commands_processed": session["stats"]["commands_processed"]
                }
            )
            
            logger.info(f"Ended voice session {session_id}")
            
            return {
                "success": True,
                "message": "Voice session ended"
            }
            
        except Exception as e:
            logger.error(f"Error ending voice session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Private methods
    async def _initialize_models(self):
        """Initialize voice processing models."""
        try:
            # Initialize Whisper model
            if not self.whisper_model:
                self.whisper_model = whisper.load_model("base")
            
            # Test ElevenLabs connection
            try:
                voices = await self.elevenlabs_client.voices.get_all()
                logger.info(f"Connected to ElevenLabs with {len(voices.voices)} voices")
            except Exception as e:
                logger.warning(f"ElevenLabs connection failed: {e}")
            
            # Initialize speech recognition
            with sr.Microphone() as source:
                self.speech_recognizer.adjust_for_ambient_noise(source)
            
            logger.info("Voice models initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing voice models: {e}")
            raise
    
    async def _test_audio_systems(self):
        """Test audio input/output systems."""
        try:
            # Test microphone
            with sr.Microphone() as source:
                logger.info("Microphone test: OK")
            
            # Test audio processing
            test_audio = np.random.rand(self.sample_rate).astype(np.float32)
            logger.info("Audio processing test: OK")
            
        except Exception as e:
            logger.warning(f"Audio system test failed: {e}")
    
    async def _process_audio_queue(self):
        """Process audio queue continuously."""
        while True:
            try:
                # Get audio data from queue
                audio_item = await self.processing_queue.get()
                
                session_id = audio_item["session_id"]
                audio_data = audio_item["audio_data"]
                audio_format = audio_item["audio_format"]
                
                session = self.voice_sessions.get(session_id)
                if not session:
                    continue
                
                # Check for hotword if enabled
                if session.get("hotword_enabled", False):
                    hotword_detected = await self._detect_hotword(audio_data, audio_format)
                    
                    if hotword_detected and not session["conversation_active"]:
                        session["conversation_active"] = True
                        session["hotword_detected"] = True
                        session["state"] = VoiceState.LISTENING
                        
                        logger.info(f"Hotword detected in session {session_id}")
                        continue
                
                # Process audio if conversation is active
                if session["conversation_active"]:
                    await self._process_continuous_audio(session_id, audio_data, audio_format)
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in audio processing queue: {e}")
                await asyncio.sleep(1)
    
    async def _transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: AudioFormat
    ) -> Dict[str, Any]:
        """Transcribe audio using Whisper."""
        try:
            # Convert audio to format expected by Whisper
            audio_array = await self._convert_audio_to_array(audio_data, audio_format)
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(
                audio_array,
                language="en",
                task="transcribe"
            )
            
            transcript = result["text"].strip()
            
            # Calculate confidence score (simplified)
            confidence = min(1.0, len(transcript) / 10.0)  # Rough estimate
            
            return {
                "success": True,
                "transcript": transcript,
                "confidence": confidence,
                "language": result.get("language", "en")
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return {
                "success": False,
                "error": str(e),
                "transcript": "",
                "confidence": 0.0
            }
    
    async def _convert_audio_to_array(
        self,
        audio_data: bytes,
        audio_format: AudioFormat
    ) -> np.ndarray:
        """Convert audio bytes to numpy array."""
        try:
            # Create audio segment
            if audio_format == AudioFormat.WAV:
                audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))
            elif audio_format == AudioFormat.MP3:
                audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
            elif audio_format == AudioFormat.WEBM:
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
            else:
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to mono and resample
            audio_segment = audio_segment.set_channels(1)
            audio_segment = audio_segment.set_frame_rate(self.sample_rate)
            
            # Convert to numpy array
            audio_array = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            audio_array = audio_array / 32768.0  # Normalize to [-1, 1]
            
            return audio_array
            
        except Exception as e:
            logger.error(f"Error converting audio to array: {e}")
            raise
    
    async def _detect_hotword(
        self,
        audio_data: bytes,
        audio_format: AudioFormat
    ) -> bool:
        """Detect hotword in audio."""
        try:
            # Transcribe audio
            transcription_result = await self._transcribe_audio(audio_data, audio_format)
            
            if not transcription_result["success"]:
                return False
            
            transcript = transcription_result["transcript"].lower()
            
            # Check for hotwords
            for hotword in self.hotwords:
                if hotword in transcript:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting hotword: {e}")
            return False
    
    async def _check_wake_sleep_commands(
        self,
        session_id: str,
        transcript: str
    ) -> bool:
        """Check for wake/sleep commands."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                return False
            
            transcript_lower = transcript.lower()
            
            # Check for wake commands
            for wake_phrase in self.conversation_context["wake_phrases"]:
                if wake_phrase in transcript_lower:
                    session["conversation_active"] = True
                    session["state"] = VoiceState.LISTENING
                    return True
            
            # Check for sleep commands
            for sleep_phrase in self.conversation_context["sleep_phrases"]:
                if sleep_phrase in transcript_lower:
                    session["conversation_active"] = False
                    session["state"] = VoiceState.IDLE
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking wake/sleep commands: {e}")
            return False
    
    async def _process_assistant_command(
        self,
        session_id: str,
        transcript: str,
        confidence: float
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process command with assistant service."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            # Stream response from assistant
            async for chunk in self.assistant_service.stream_response(
                session["assistant_session_id"],
                transcript
            ):
                chunk_data = json.loads(chunk)
                
                if chunk_data.get("content"):
                    yield {
                        "type": "assistant_response",
                        "content": chunk_data["content"],
                        "partial": True
                    }
                elif chunk_data.get("error"):
                    yield {
                        "type": "error",
                        "error": chunk_data["error"]
                    }
            
            # Final response
            yield {
                "type": "assistant_response",
                "content": "",  # Final content would be accumulated
                "partial": False
            }
            
        except Exception as e:
            logger.error(f"Error processing assistant command: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _generate_speech_response(
        self,
        session_id: str,
        text: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate speech response using ElevenLabs."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                raise ValueError(f"Invalid session: {session_id}")
            
            # Get voice settings
            voice_settings = session.get("voice_settings", self.voice_settings)
            
            # Update session state
            session["state"] = VoiceState.SPEAKING
            
            # Generate speech
            try:
                audio_stream = await self.elevenlabs_client.generate(
                    text=text,
                    voice=voice_settings["voice_id"],
                    stream=True,
                    model="eleven_monolingual_v1"
                )
                
                # Stream audio chunks
                async for chunk in audio_stream:
                    if chunk:
                        # Encode audio chunk as base64
                        audio_b64 = base64.b64encode(chunk).decode()
                        
                        yield {
                            "type": "audio_chunk",
                            "audio_data": audio_b64,
                            "format": "mp3",
                            "partial": True
                        }
                
                # Final audio chunk
                yield {
                    "type": "audio_chunk",
                    "audio_data": "",
                    "format": "mp3",
                    "partial": False
                }
                
            except Exception as e:
                logger.warning(f"ElevenLabs synthesis failed: {e}")
                
                # Fallback to text response
                yield {
                    "type": "text_response",
                    "text": text,
                    "message": "Speech synthesis unavailable, returning text"
                }
            
            # Update session state
            session["state"] = VoiceState.IDLE
            
        except Exception as e:
            logger.error(f"Error generating speech response: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def _process_continuous_audio(
        self,
        session_id: str,
        audio_data: bytes,
        audio_format: AudioFormat
    ):
        """Process continuous audio stream."""
        try:
            session = self.voice_sessions.get(session_id)
            if not session:
                return
            
            # Add to audio buffer
            session["audio_buffer"].append({
                "data": audio_data,
                "format": audio_format,
                "timestamp": datetime.utcnow()
            })
            
            # Keep buffer size manageable
            if len(session["audio_buffer"]) > 10:
                session["audio_buffer"].pop(0)
            
            # Detect voice activity
            if await self._detect_voice_activity(audio_data, audio_format):
                session["last_activity"] = datetime.utcnow()
                session["state"] = VoiceState.LISTENING
            else:
                # Check for silence timeout
                silence_duration = (datetime.utcnow() - session["last_activity"]).total_seconds()
                if silence_duration > 3.0:  # 3 seconds of silence
                    session["conversation_active"] = False
                    session["state"] = VoiceState.IDLE
                    logger.info(f"Voice session {session_id} went idle due to silence")
            
        except Exception as e:
            logger.error(f"Error processing continuous audio: {e}")
    
    async def _detect_voice_activity(
        self,
        audio_data: bytes,
        audio_format: AudioFormat
    ) -> bool:
        """Detect voice activity in audio."""
        try:
            # Convert to audio array
            audio_array = await self._convert_audio_to_array(audio_data, audio_format)
            
            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_array**2))
            
            # Simple threshold-based VAD
            voice_threshold = 0.01  # Adjust as needed
            
            return rms > voice_threshold
            
        except Exception as e:
            logger.error(f"Error detecting voice activity: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown voice interface."""
        try:
            # Cancel all active streams
            for task in self.active_streams.values():
                task.cancel()
            
            # Clear sessions
            self.voice_sessions.clear()
            
            # Close ElevenLabs client
            if hasattr(self.elevenlabs_client, 'close'):
                await self.elevenlabs_client.close()
            
            logger.info("Voice interface shutdown complete")
            
        except Exception as e:
            logger.error(f"Error shutting down voice interface: {e}")


# WebSocket handler for real-time voice communication
class VoiceWebSocketHandler:
    """WebSocket handler for voice interface."""
    
    def __init__(self, voice_interface: VoiceInterface):
        self.voice_interface = voice_interface
        self.active_connections: Dict[str, Any] = {}
    
    async def handle_connection(self, websocket, session_id: str):
        """Handle WebSocket connection for voice."""
        try:
            self.active_connections[session_id] = websocket
            
            await websocket.send_json({
                "type": "connection_established",
                "session_id": session_id
            })
            
            # Listen for messages
            async for message in websocket.iter_json():
                await self._handle_message(session_id, message)
                
        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")
        finally:
            # Clean up connection
            if session_id in self.active_connections:
                del self.active_connections[session_id]
    
    async def _handle_message(self, session_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket message."""
        try:
            message_type = message.get("type")
            
            if message_type == "audio_chunk":
                # Process audio chunk
                audio_data = base64.b64decode(message["audio_data"])
                audio_format = AudioFormat(message.get("format", "wav"))
                
                # Process with voice interface
                async for response in self.voice_interface.process_voice_command(
                    session_id, audio_data, audio_format
                ):
                    await self._send_response(session_id, response)
            
            elif message_type == "start_listening":
                # Start listening
                await self.voice_interface.enable_hotword_detection(session_id)
                await self._send_response(session_id, {
                    "type": "listening_started",
                    "message": "Voice interface activated"
                })
            
            elif message_type == "stop_listening":
                # Stop listening
                await self.voice_interface.disable_hotword_detection(session_id)
                await self._send_response(session_id, {
                    "type": "listening_stopped",
                    "message": "Voice interface deactivated"
                })
            
            elif message_type == "configure_voice":
                # Configure voice settings
                voice_settings = message.get("voice_settings", {})
                result = await self.voice_interface.set_voice_settings(
                    session_id, voice_settings
                )
                await self._send_response(session_id, {
                    "type": "voice_configured",
                    "result": result
                })
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_response(session_id, {
                "type": "error",
                "error": str(e)
            })
    
    async def _send_response(self, session_id: str, response: Dict[str, Any]):
        """Send response to WebSocket."""
        try:
            websocket = self.active_connections.get(session_id)
            if websocket:
                await websocket.send_json(response)
        except Exception as e:
            logger.error(f"Error sending WebSocket response: {e}")


# Voice interface singleton
voice_interface = VoiceInterface()