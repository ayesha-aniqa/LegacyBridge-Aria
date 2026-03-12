import os
import logging
from google.cloud import texttospeech
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logger = logging.getLogger("aria.tts")

class AriaTTS:
    def __init__(self):
        try:
            self.client = texttospeech.TextToSpeechClient()
            self.voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Wavenet-F",  # Warm, natural female voice
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            )
            self.audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.85,  # Slower for elderly users (approx 140 wpm)
                pitch=0.0,
            )
            logger.info("Google Cloud TTS initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud TTS: {e}")
            self.client = None

    def speak(self, text: str):
        """Synthesize speech and play it using a local player."""
        if not self.client:
            print(f"TTS offline. Aria would say: {text}")
            return

        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            response = self.client.synthesize_speech(
                input=synthesis_input, voice=self.voice, audio_config=self.audio_config
            )

            # Save to temporary file
            temp_file = "aria_guidance.mp3"
            with open(temp_file, "wb") as out:
                out.write(response.audio_content)

            # Play the file
            # On Windows, we can use 'start', on Linux 'mpg123' or 'play'
            if os.name == 'nt':
                os.system(f"start /min {temp_file}")
            else:
                os.system(f"mpg123 -q {temp_file} &")

        except Exception as e:
            logger.error(f"TTS Synthesis Error: {e}")
