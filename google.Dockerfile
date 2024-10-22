# google.Dockerfile

FROM python:3.11.9-slim-bookworm

# Set environment variable to avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

COPY requirements.txt /app/requirements.txt

# Install required Python libraries
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set the working directory in the container
WORKDIR /app

# Copy your Python app into the container
COPY . /app

# Make sure the secret file is mounted, so we avoid putting it in the image
CMD ["python", "texttospeech.py"]
