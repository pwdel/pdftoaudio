import os
from google.cloud import texttospeech


def test_google_tts():
    # Authenticate using the service account key
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/secrets/key.json'

    try:
        # Read the contents of the test.txt file
        with open("../text/test.txt", "r") as file:
            text_content = file.read()

        if not text_content.strip():
            print("Error: The input text file is empty.")
            return

        # Initialize the Text-to-Speech client
        client = texttospeech.TextToSpeechClient()

        # Define the text input
        synthesis_input = texttospeech.SynthesisInput(text=text_content)

        # Select the voice parameters, using "en-US-Casual-K"
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Casual-K"  # Use the Casual K voice
        )

        # Define the audio output configuration
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Perform the text-to-speech request
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )

        # Save the output to an MP3 file
        with open("/audio/test_audio.mp3", "wb") as out:
            out.write(response.audio_content)
            print("Audio content written to /output/test_audio.mp3")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    test_google_tts()
