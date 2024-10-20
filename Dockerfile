FROM python:3.13-slim-bookworm

# Set working directory in the container
WORKDIR /app

# Install pypdf
RUN pip install pypdf

# This is where your code will go in the mounted directory
CMD ["python"]
