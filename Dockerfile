FROM python:3.11-slim

WORKDIR /app

# Install required Python packages
# plexapi>=4.15.0 includes fix for deprecated friend removal endpoint (PR #1413)
RUN pip install --no-cache-dir requests python-dateutil 'plexapi>=4.15.0'

# Create state directory
RUN mkdir -p /app/state

# Copy application code
COPY main.py /app/

# Run the application
CMD ["python", "-u", "main.py"]
