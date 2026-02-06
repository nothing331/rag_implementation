# Troubleshooting Guide

## Common Issues and Solutions

### Query Returns No Results

**Symptoms:**
- Empty sources array
- "I couldn't find relevant information"
- Generic response without citations

**Possible Causes:**
1. Documents not ingested
2. Query too specific or vague
3. Vector store corruption
4. Embedding model mismatch

**Solutions:**

1. **Check document ingestion status:**
```bash
curl https://api.cloudsync.com/api/v1/ingest/status
```

2. **Re-ingest documents:**
```bash
curl -X POST https://api.cloudsync.com/api/v1/ingest \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"force": true}'
```

3. **Check vector store health:**
```bash
# Verify Chroma DB
ls -la data/chroma_db/
# Should show: chroma.sqlite3, index/

# Check document count
curl https://api.cloudsync.com/health
```

4. **Test with simpler query:**
Try "What is CloudSync?" instead of complex technical questions.

### Slow Response Times

**Symptoms:**
- Response takes > 10 seconds
- Timeout errors
- High latency in metadata

**Possible Causes:**
1. LLM API rate limiting
2. Large document set
3. Inefficient query planning
4. Network issues

**Solutions:**

1. **Check Groq API status:**
```bash
# Test API directly
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY"
```

2. **Enable streaming:**
Use `/api/v1/query/stream` for better perceived performance.

3. **Reduce max_sources:**
Set to 3 instead of default 5 to reduce token usage.

4. **Use smaller model:**
Switch to `llama-3.1-8b-instant` for faster responses.

5. **Check network latency:**
```bash
# Test connection to vector store
time curl https://api.cloudsync.com/health
```

### Validation Agent Rejects All Chunks

**Symptoms:**
- Low confidence scores (< 0.6)
- Multiple re-retrieval attempts
- Sources appear irrelevant

**Possible Causes:**
1. Query misunderstood by planner
2. Documents don't cover topic
3. Validation threshold too strict
4. Wrong embedding model

**Solutions:**

1. **Adjust validation threshold:**
```env
VALIDATION_THRESHOLD=0.5  # Lower from 0.6
```

2. **Check query decomposition:**
Enable debug logging to see sub-queries:
```env
LOG_LEVEL=DEBUG
```

3. **Verify document coverage:**
Ensure relevant docs are in `/docs/` and ingested.

4. **Test embedding quality:**
```python
# Manual similarity check
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
query_emb = model.encode("How do I deploy to AWS?")
doc_emb = model.encode("AWS deployment guide content...")

similarity = cosine_similarity([query_emb], [doc_emb])
print(f"Similarity: {similarity[0][0]}")
```

### High Token Usage

**Symptoms:**
- Tokens_used > 2000 per query
- Rising API costs
- Context length warnings

**Possible Causes:**
1. Too many chunks retrieved
2. Large chunk size
3. Complex multi-hop queries
4. No query caching

**Solutions:**

1. **Reduce chunk count:**
```env
MAX_RETRIEVAL_CHUNKS=5  # Down from 10
```

2. **Smaller chunks:**
```env
CHUNK_SIZE=300  # Down from 500
CHUNK_OVERLAP=30
```

3. **Enable query cache:**
```env
ENABLE_QUERY_CACHE=true
```

4. **Use cheaper model for validation:**
```env
VALIDATOR_MODEL=llama-3.1-8b-instant
```

### Application Won't Start

**Symptoms:**
- Error on startup
- Missing dependencies
- Environment variable errors

**Common Errors:**

**"Missing required environment variable: GROQ_API_KEY"**
```bash
# Solution
cp .env.example .env
# Edit .env and add your Groq API key
```

**"Failed to connect to vector store"**
```bash
# Create data directory
mkdir -p data/chroma_db

# Check permissions
chmod 755 data/
```

**"Module not found: sentence_transformers"**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
python -c "import sentence_transformers; print('OK')"
```

**"Port 8000 already in use"**
```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

### Database Connection Errors

**Symptoms:**
- "Connection refused" errors
- Timeout when connecting to PostgreSQL
- Pool exhausted errors

**Solutions:**

1. **Verify PostgreSQL is running:**
```bash
docker-compose ps postgres
# Should show: Up (healthy)
```

2. **Check DATABASE_URL format:**
Must be: `postgresql://user:password@host:port/database`

3. **Increase connection pool:**
```env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
```

4. **Test connection manually:**
```bash
psql $DATABASE_URL -c "SELECT 1;"
```

### Redis Connection Issues

**Symptoms:**
- "Redis connection error"
- Celery tasks not processing
- Cache not working

**Solutions:**

1. **Verify Redis is running:**
```bash
docker-compose exec redis redis-cli ping
# Should return: PONG
```

2. **Check REDIS_URL format:**
Should be: `redis://host:port/db_number`

3. **Clear Redis and restart:**
```bash
docker-compose exec redis redis-cli FLUSHALL
docker-compose restart redis
```

### Response Quality Issues

**Symptoms:**
- Hallucinated information
- Wrong citations
- Outdated answers
- Missing key details

**Solutions:**

1. **Update documents:**
Ensure docs reflect current system state.

2. **Check source quality:**
Review `content_preview` in response to verify chunks.

3. **Use larger model:**
```env
SYNTHESIZER_MODEL=llama-3.1-70b-versatile
```

4. **Lower temperature:**
```env
SYNTHESIZER_TEMPERATURE=0.1  # More deterministic
```

5. **Add more context:**
Include user role or context in query:
```json
{
  "query": "How do I deploy? (I'm a backend developer)"
}
```

### Security Warnings

**"JWT secret too short"**
```bash
# Generate strong secret
openssl rand -hex 32
# Add to .env
```

**"Insecure CORS origins"**
```env
# Don't use wildcards in production
CORS_ORIGINS=https://app.cloudsync.com,https://admin.cloudsync.com
```

**"Debug mode enabled in production"**
```env
DEBUG=false
ENVIRONMENT=production
```

## Debugging Tips

### Enable Detailed Logging

```env
LOG_LEVEL=DEBUG
```

View logs:
```bash
# Docker
docker-compose logs -f api

# Local
uvicorn app.main:app --log-level debug
```

### Test Individual Agents

```python
# test_planner.py
from app.agents.planner import QueryPlanner

planner = QueryPlanner()
result = planner.plan("How do I deploy to AWS?")
print(result)

# test_retriever.py
from app.agents.retriever import RetrieverAgent

retriever = RetrieverAgent()
chunks = retriever.retrieve_parallel([{"text": "AWS deployment"}])
print(f"Found {len(chunks)} chunks")
```

### Monitor Token Usage

Check metadata in every response:
```json
{
  "metadata": {
    "tokens_used": 450,
    "processing_time_ms": 1250
  }
}
```

Set up alerts if tokens_used > 2000 consistently.

### Performance Profiling

```python
# Add timing to pipeline
import time

async def process_with_timing(query):
    start = time.time()
    result = await pipeline.process(query)
    print(f"Total time: {(time.time() - start) * 1000:.0f}ms")
    return result
```

## Getting Help

If issues persist:

1. **Check logs** for stack traces
2. **Review recent changes** in git
3. **Test in isolation** (single agent)
4. **Check dependencies** versions
5. **File an issue** with:
   - Error message
   - Steps to reproduce
   - Environment details
   - Relevant logs