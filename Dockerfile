FROM python:3.11-slim

WORKDIR /app

# Install git (needed for GitPython)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application
COPY src/ src/

# Expose webhook port
EXPOSE 8080

# Default command: start webhook server
CMD ["python", "-m", "src.cli", "server", "--port", "8080"]
