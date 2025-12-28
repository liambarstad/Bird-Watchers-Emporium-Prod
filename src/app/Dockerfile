FROM python:3.12-alpine

WORKDIR /app

# Default environment configuration for container runtime
# These can be overridden by Helm/Kubernetes env vars if needed.
ENV APP_ENV=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Install system dependencies (Alpine uses apk, not apt)
RUN apk add --no-cache gcc musl-dev linux-headers

# Copy application code
COPY . .

# Install the application
RUN pip install --no-cache-dir -e .

# Create non-root user (Alpine uses adduser)
RUN adduser -D -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose application port (kept in sync with API_PORT above)
EXPOSE ${API_PORT}

# Health check (uses API_PORT so it stays in sync if overridden)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, requests; port = os.getenv('API_PORT', '8000'); requests.get('http://localhost:' + port + '/health')" || exit 1

# Default command (adjust based on your entry point)
CMD ["python", "-m", "main"]

