# google.Dockerfile

FROM python:3.13-slim-bookworm

# Set environment variable to avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install required Python libraries
RUN pip install --no-cache-dir google-cloud-texttospeech

# Set the working directory in the container
WORKDIR /app

# Copy your Python app into the container
COPY . /app

# Make sure the secret file is mounted, so we avoid putting it in the image
CMD ["python", "texttospeech.py"]
