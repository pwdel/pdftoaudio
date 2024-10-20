import os
from google.cloud import texttospeech
import sys


def text_to_speech(input_txt_file: str):
    """
    Convert text from a file to speech using Google's Text-to-Speech API and save as an audio file.

    :param input_txt_file: Path to the input .txt file.
    """
    # Authenticate using the service account key (already mounted)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/secrets/key.json'

    # Get the output file name by replacing the .txt extension with .mp3
    output_audio_file = os.path.splitext(input_txt_file)[0] + ".mp3"

    # Check if input text file exists
    if not os.path.exists(input_txt_file):
        print(f"Error: The file '{input_txt_file}' does not exist.")
        return

    try:
        # Initialize the Text-to-Speech client
        client = texttospeech.TextToSpeechClient()

        # Read the input text file
        with open(input_txt_file, 'r') as file:
            text_content = file.read()

        if not text_content.strip():
            print("Error: The input text file is empty.")
            return

        print(f"Converting text from '{input_txt_file}' to speech...")

        # Set up the input for the TTS request
        synthesis_input = texttospeech.SynthesisInput(text=text_content)

        # Select the voice parameters (you can customize this)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-US",  # Set the language (you can change this to other languages)
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL  # Set voice gender (NEUTRAL, MALE, FEMALE)
        )

        # Set the audio file format to MP3
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Send the request to Google Text-to-Speech API
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice_params, audio_config=audio_config
        )

        # Save the output as an MP3 file
        with open(output_audio_file, 'wb') as out:
            out.write(response.audio_content)
            print(f"Audio content written to '{output_audio_file}'.")

    except Exception as e:
        print(f"An error occurred: {e}")


# Example usage of the function from command-line argument
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python texttospeech.py <input_text_file>")
        sys.exit(1)

    input_text_file = sys.argv[1]  # Get the input text file from the first argument

    # Convert the text file to speech
    text_to_speech(input_text_file)
