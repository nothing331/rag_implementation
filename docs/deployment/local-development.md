# Local Development Setup

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- Make (optional, for convenience commands)

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourorg/cloudsync.git
cd cloudsync

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your local values:

```env
# Application
APP_NAME=CloudSync
DEBUG=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development

# Database (local PostgreSQL)
DATABASE_URL=postgresql://cloudsync:cloudsync@localhost:5432/cloudsync_dev

# Redis (local)
REDIS_URL=redis://localhost:6379/0

# JWT (generate with: openssl rand -hex 32)
JWT_SECRET=your-local-dev-secret-key-min-32-chars-long

# Groq API (get from https://console.groq.com)
GROQ_API_KEY=gsk_your_api_key_here

# AWS (optional for local dev)
AWS_REGION=us-east-1
S3_BUCKET=cloudsync-dev-files

# Vector Store
VECTOR_STORE_PATH=./data/chroma_db
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Start Infrastructure Services

Using Docker Compose for local infrastructure:

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: cloudsync
      POSTGRES_PASSWORD: cloudsync
      POSTGRES_DB: cloudsync_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cloudsync"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Optional: Local S3-compatible storage
  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

Start services:
```bash
docker-compose up -d

# Verify all services are healthy
docker-compose ps
```

### 4. Database Setup

```bash
# Run migrations
alembic upgrade head

# Seed with test data (optional)
python scripts/seed_database.py
```

### 5. Document Ingestion

```bash
# Ingest all documentation
python -m app.core.document_loader --ingest

# Or ingest specific directory
python -m app.core.document_loader --path docs/architecture
```

### 6. Start the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the provided script
make dev
```

Visit: http://localhost:8000/docs for interactive API documentation.

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint
flake8 app/ tests/

# Type checking
mypy app/

# Or run all
make lint
```

### Debugging

Enable detailed logging:
```python
# In your code
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set in `.env`:
```env
LOG_LEVEL=DEBUG
```

### Testing the RAG Pipeline

```bash
# Using curl
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I deploy to AWS?",
    "max_sources": 3
  }'

# Or use the CLI tool
python -m app.cli query "How do I deploy to AWS?"
```

## Common Issues

### Issue: PostgreSQL connection refused
**Solution:**
```bash
# Check if postgres container is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart
docker-compose restart postgres
```

### Issue: Redis connection timeout
**Solution:**
```bash
# Verify redis is healthy
docker-compose exec redis redis-cli ping

# Should return: PONG
```

### Issue: Module not found errors
**Solution:**
```bash
# Ensure you're in virtual environment
which python

# Should show: /path/to/venv/bin/python

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Port already in use
**Solution:**
```bash
# Find process using port
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

## IDE Configuration

### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance (Microsoft)
- Black Formatter
- isort
- Python Docstring Generator

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true
}
```

### PyCharm

- Set interpreter to venv
- Enable Black as formatter (Preferences → Tools → External Tools)
- Configure pytest as test runner
- Enable type checking (mypy)

## Useful Commands

```bash
# Reset database
make reset-db

# View logs
docker-compose logs -f

# Update dependencies
pip-compile requirements.in
pip-compile requirements-dev.in
pip-sync requirements.txt requirements-dev.txt

# Build production Docker image
make build

# Run security scan
make security-scan
```

## Next Steps

1. Read the [Architecture Overview](architecture/overview.md)
2. Review the [API Reference](configuration/api-reference.md)
3. Set up [pre-commit hooks](https://pre-commit.com/)
4. Join the developer Slack channel

## Support

- GitHub Issues: https://github.com/yourorg/cloudsync/issues
- Internal Slack: #cloudsync-dev
- Office Hours: Tuesdays 2-3pm PT