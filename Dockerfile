# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed (gcc may be required for some Python packages)
# Using build-essential for better compatibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* || true

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Set environment variable for production
ENV FLASK_ENV=production

# Run the application
# Cloud Run sets PORT env var automatically, default to 8080
# Use JSON format for CMD to handle signals properly
CMD ["sh", "-c", "exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 app:app"]

