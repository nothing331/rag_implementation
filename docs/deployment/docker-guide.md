# Docker Deployment Guide

## Overview

Deploy CloudSync using Docker containers for consistent environments across development, staging, and production.

## Quick Start

### 1. Build the Image

```bash
docker build -t cloudsync-api:latest .
```

### 2. Run with Docker Compose (Full Stack)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Production Dockerfile

```dockerfile
# Multi-stage build for smaller image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Security: Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser docs/ ./docs/

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Docker Compose Configurations

### Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app
      - ./docs:/app/docs
      - ./data:/app/data
    environment:
      - DEBUG=true
      - LOG_LEVEL=DEBUG
      - DATABASE_URL=postgresql://cloudsync:cloudsync@postgres:5432/cloudsync_dev
      - REDIS_URL=redis://redis:6379/0
      - GROQ_API_KEY=${GROQ_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: cloudsync
      POSTGRES_PASSWORD: cloudsync
      POSTGRES_DB: cloudsync_dev
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cloudsync"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

### Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - LOG_LEVEL=INFO
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET=${JWT_SECRET}
      - GROQ_API_KEY=${GROQ_API_KEY}
      - AWS_REGION=${AWS_REGION}
      - S3_BUCKET=${S3_BUCKET}
      - VECTOR_STORE_PATH=/app/data/chroma_db
    volumes:
      - chroma_data:/app/data
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api

  # Run ingestion on startup
  ingest:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - VECTOR_STORE_PATH=/app/data/chroma_db
    volumes:
      - chroma_data:/app/data
      - ./docs:/app/docs:ro
    command: python -m app.core.document_loader --ingest
    restart: "no"
    depends_on: []

volumes:
  chroma_data:
```

## Multi-Stage Build Explained

### Stage 1: Builder
- Uses full Python image with build tools
- Installs all dependencies
- Creates wheels for faster installation

### Stage 2: Production
- Uses slim Python image (smaller attack surface)
- Copies only installed packages from builder
- Runs as non-root user
- No build tools in final image

**Size Comparison:**
- Single-stage: ~1.2GB
- Multi-stage: ~450MB
- With `python:3.11-alpine`: ~280MB (but may have compatibility issues)

## Container Security Best Practices

1. **Non-root user**: All containers run as `appuser` (uid 1000)
2. **Read-only filesystem**: Mount volumes for writable areas only
3. **No secrets in images**: Use environment variables or secrets management
4. **Minimal base image**: Use `slim` variant, not `latest`
5. **Health checks**: All services have defined health checks
6. **Resource limits**: CPU and memory limits set
7. **No build tools**: Compilers and dev tools not in production image

## Optimizing Build Performance

```dockerfile
# Use BuildKit for faster builds
# export DOCKER_BUILDKIT=1

# Leverage build cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy application code LAST (changes most frequently)
COPY . .

# Use .dockerignore
# .git
# __pycache__
# *.pyc
# .env
# data/
# *.md
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs api

# Check environment variables
docker-compose exec api env

# Interactive debugging
docker-compose run --rm api bash
```

### High memory usage
```bash
# Monitor container stats
docker stats

# Check memory in container
docker-compose exec api ps aux --sort=-%mem
```

### Slow startup
- Health check start period may need increasing
- Document ingestion on startup can be slow
- Consider pre-populated volume for Chroma DB

## Advanced: Kubernetes Deployment

For production at scale, see [AWS Deployment Guide](aws-setup.md) for ECS, or use Kubernetes:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudsync-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cloudsync
  template:
    metadata:
      labels:
        app: cloudsync
    spec:
      containers:
      - name: api
        image: cloudsync-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: cloudsync-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Performance Tuning

### Gunicorn Workers
```
workers = (2 × CPU cores) + 1
# For 2 vCPU: 5 workers
# For 4 vCPU: 9 workers
```

### Uvicorn vs Gunicorn
- **Uvicorn**: Faster, async-native, good for I/O bound workloads
- **Gunicorn**: More stable, better for CPU-bound, easier to configure

**Recommendation**: Use Uvicorn with multiple workers for RAG applications (I/O heavy).

### Connection Pooling
```python
# database.py
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=10,              # Default connections
    max_overflow=20,           # Extra when busy
    pool_timeout=30,           # Wait for connection
    pool_recycle=1800,         # Recycle after 30 min
    pool_pre_ping=True,        # Verify connection health
)
```