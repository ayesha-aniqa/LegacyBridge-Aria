import os
import logging
from google.cloud import texttospeech
from dotenv import load_dotenv
from playsound import playsound
import threading
import tempfile

load_dotenv()

logger = logging.getLogger("aria.tts")


class AriaTTS:
    def __init__(self):
        try:
            self.client = texttospeech.TextToSpeechClient()
            self.voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Wavenet-F",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            )
            self.audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.85,
                pitch=0.0,
            )
            self.audio_thread = None
            logger.info("Google Cloud TTS initialized.")
        except Exception as e:
            print(f"TTS Init Error: {e}")
            self.client = None

    def speak(self, text: str):
        if not self.client:
            print(f"TTS offline. Aria would say: {text}")
            return

        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config,
            )

            # Stop previous TTS if running
            self.stop()

            # Use a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_file.write(response.audio_content)
                tmp_file_path = tmp_file.name

            # Play in a separate thread to avoid blocking UI
            def play_audio(file_path):
                try:
                    playsound(file_path)
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)

            self.audio_thread = threading.Thread(
                target=play_audio, args=(tmp_file_path,), daemon=True
            )
            self.audio_thread.start()

        except Exception as e:
            print(f"TTS Speak Error: {e}")

    def stop(self):
        try:
            if self.audio_thread and self.audio_thread.is_alive():
                # Can't forcibly stop playsound, but future plays won't clash
                print("Stopping TTS playback...")
        except Exception as e:
            print(f"TTS Stop Error: {e}")