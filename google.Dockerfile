# syntax = docker/dockerfile:1.6

FROM python:3.11.9-slim-bookworm

# Set environment variable to avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

COPY requirements.txt /app/requirements.txt

RUN <<EOF
    apt-get update
    apt-get upgrade -y
    apt-get install -y --no-install-recommends \
        ffmpeg
    apt-get clean
    rm -rf /var/lib/apt/lists/*
EOF

# Install required Python libraries
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set the working directory in the container
WORKDIR /app

# Copy your Python app into the container
COPY . /app