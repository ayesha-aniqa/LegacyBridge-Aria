import os
import queue
import logging
import threading
from google.cloud import speech
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logger = logging.getLogger("aria.stt")

class AriaVoiceInput:
    """
    Streaming speech-to-text listener for Aria.
    Listens for 'Aria' or 'Help me' as wake words.
    """
    def __init__(self, callback):
        self.callback = callback # Function to call with transcribed text
        self.client = speech.SpeechClient()
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
        )
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=self.config,
            interim_results=True,
        )
        self.audio_queue = queue.Queue()
        self.listening = False

    def start_listening(self):
        """Start the streaming recognition in a background thread."""
        self.listening = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        logger.info("Voice input listener started.")

    def stop_listening(self):
        self.listening = False
        logger.info("Voice input listener stopped.")

    def _listen_loop(self):
        # Note: This is a simplified version. For a real production app, 
        # we'd use PyAudio to stream from the microphone.
        # Since we don't have PyAudio in the requirements yet, I'll assume 
        # it's added or mock the streaming for now.
        
        # Real implementation would stream audio chunks into self.audio_queue
        # then yield them here.
        pass

    def mock_voice_command(self, text):
        """Simulate a voice command for demo purposes."""
        logger.info(f"Simulated Voice Command: {text}")
        self.callback(text)
