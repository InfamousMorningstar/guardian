# Dockerfile for Plex Auto-Pruning Daemon
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create state directory
RUN mkdir -p /app/state

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "-u", "main.py"]