FROM python:3.11

WORKDIR /app

# python:3.11 (non-slim) already has git installed

# Install dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ src/
COPY pyproject.toml .

# Set PYTHONPATH so src module is importable
ENV PYTHONPATH=/app

# Expose webhook port
EXPOSE 8080

# Default command: start webhook server
CMD ["python", "-m", "src.cli", "server", "--port", "8080"]
