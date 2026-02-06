# CloudSync RAG - Agentic Technical Documentation Assistant

An intelligent RAG (Retrieval-Augmented Generation) system with multi-agent architecture for answering technical documentation queries. Built with FastAPI, ChromaDB, and Groq LLM.

## Architecture Overview

```
User Query → [Query Planner] → [Parallel Retriever] → [Validator] → [Synthesizer] → Response
                ↓                      ↓                  ↓            ↓
           Decomposes            Searches           Validates    Generates
           into sub-queries      vector store       chunks       final answer
```

### Agents

1. **Query Planner**: Breaks complex queries into parallel, atomic sub-queries
2. **Retriever Agent**: Performs parallel vector search for all sub-queries
3. **Validator Agent**: Validates retrieved chunks with medium strictness (threshold: 0.6)
4. **Synthesizer Agent**: Generates coherent responses with inline citations

## Quick Start

### Prerequisites

- Python 3.11+
- Groq API key (get from https://console.groq.com)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd rag_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### Run the Application

```bash
# Start the API server
uvicorn app.main:app --reload

# Or use the provided script
python -m app.main
```

The API will be available at `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

## API Endpoints

### Query Documents

**POST** `/api/v1/query`

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I deploy to AWS with Docker?",
    "max_sources": 3
  }'
```

**Response:**
```json
{
  "answer": "To deploy CloudSync to AWS with Docker...",
  "sources": [
    {
      "document": "deployment/aws-setup.md",
      "section": "Step-by-Step Deployment",
      "relevance_score": 0.94,
      "content_preview": "Build & Push Docker Image..."
    }
  ],
  "metadata": {
    "processing_time_ms": 1250,
    "tokens_used": 450,
    "confidence": 0.92,
    "sub_queries": ["Find AWS deployment steps"]
  }
}
```

### Health Check

**GET** `/health`

```bash
curl http://localhost:8000/health
```

### Document Ingestion

**POST** `/api/v1/ingest`

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

## Sample Documentation

The `/docs` folder contains 7 technical documentation files for testing:

- **Architecture**: System overview, data flow, scalability
- **Deployment**: AWS setup, Docker guide, local development
- **Configuration**: Environment variables, API reference, troubleshooting

## Project Structure

```
rag_agent/
├── app/
│   ├── agents/           # Agent implementations
│   │   ├── planner.py    # Query decomposition
│   │   ├── retriever.py  # Vector search
│   │   ├── validator.py  # Relevance validation
│   │   └── synthesizer.py # Response generation
│   ├── core/             # Core functionality
│   │   ├── document_loader.py  # Markdown parsing
│   │   ├── embeddings.py       # Embedding generation
│   │   ├── vector_store.py     # ChromaDB wrapper
│   │   └── pipeline.py         # Orchestration
│   ├── utils/
│   │   └── logger.py     # Structured logging
│   ├── config.py         # Configuration
│   ├── models.py         # Pydantic models
│   └── main.py           # FastAPI app
├── docs/                 # Sample documentation
├── tests/                # Test suite
├── requirements.txt      # Dependencies
├── .env.example          # Environment template
└── README.md             # This file
```

## Configuration

All configuration is done via environment variables (see `.env.example`):

### Required
- `GROQ_API_KEY`: Your Groq API key

### Optional
- `PLANNER_MODEL`: LLM for query planning (default: llama-3.1-70b-versatile)
- `VALIDATOR_MODEL`: LLM for validation (default: llama-3.1-70b-versatile)
- `SYNTHESIZER_MODEL`: LLM for synthesis (default: llama-3.1-70b-versatile)
- `CHUNK_SIZE`: Document chunk size in tokens (default: 500)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 50)
- `VALIDATION_THRESHOLD`: Minimum confidence for valid chunks (default: 0.6)
- `MAX_RETRIEVAL_CHUNKS`: Maximum chunks to retrieve (default: 10)

## How It Works

### 1. Query Planning
The Planner Agent analyzes the user query and decomposes it into 1-4 parallel sub-queries. For example:
- Input: "How do I deploy to AWS with Docker?"
- Output: `["AWS deployment prerequisites", "Docker build instructions", "ECS configuration"]`

### 2. Parallel Retrieval
The Retriever Agent executes all sub-queries in parallel against the vector store:
- Generates embeddings for each sub-query
- Searches ChromaDB using cosine similarity
- Returns top-K chunks per query
- Deduplicates results

### 3. Validation
The Validator Agent checks each retrieved chunk:
- Medium strictness: threshold of 0.6
- Calculates confidence scores based on keyword overlap and vector similarity
- Identifies missing topics
- Triggers re-retrieval if coverage < 3 chunks or high-priority topics missing

### 4. Synthesis
The Synthesizer Agent generates the final response:
- Takes top 5 validated chunks as context
- Generates answer with inline citations [1], [2], etc.
- Streams tokens for better UX (optional)
- Includes source metadata

## Performance Characteristics

- **p50 Latency**: ~1.5 seconds (query → response)
- **p95 Latency**: ~3 seconds
- **Token Usage**: ~400-600 tokens per query
- **Throughput**: ~20 queries/minute (depends on Groq rate limits)

## Scaling Considerations

### Current Limitations (Prototype)
- Single-node ChromaDB (file-based)
- In-memory document ingestion
- No query caching
- No user sessions

### Production Enhancements
1. **Distributed Vector DB**: Migrate to Pinecone/Qdrant
2. **Query Cache**: Redis-based caching for common queries
3. **Async Processing**: Queue-based ingestion pipeline
4. **Load Balancing**: Multiple API instances behind LB
5. **Streaming**: SSE for real-time responses

See `/docs/architecture/scalability.md` for detailed scaling strategies.

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### Sample Test Queries

1. Simple: "What database does CloudSync use?"
2. Multi-hop: "How do I deploy to AWS and what environment variables do I need?"
3. Complex: "Explain the data flow from client sync to database storage"

## Cost Optimization

Current setup costs (estimates):
- **Groq API**: ~$0.02-0.05 per query (using 70B model)
- **Embeddings**: Local (free with sentence-transformers)
- **Storage**: ChromaDB local files (~10MB for sample docs)

To reduce costs:
1. Use `llama-3.1-8b-instant` for non-critical agents (70% cheaper)
2. Implement query caching (save ~40% on repeated queries)
3. Reduce `MAX_RETRIEVAL_CHUNKS` to 5 (fewer tokens)
4. Smaller chunks (300 tokens instead of 500)

## Troubleshooting

### "Vector store empty" error
```bash
# Ingest documents
curl -X POST http://localhost:8000/api/v1/ingest -d '{"force": true}'
```

### "Groq API key invalid"
- Verify key starts with `gsk_`
- Check key has credits at https://console.groq.com

### High latency
- Use smaller model: `SYNTHESIZER_MODEL=llama-3.1-8b-instant`
- Reduce `MAX_RETRIEVAL_CHUNKS` to 5
- Enable streaming endpoint

### No relevant results
- Check documents are in `/docs` directory
- Verify documents are Markdown format
- Increase `VALIDATION_THRESHOLD` (e.g., 0.5 for more lenient)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

MIT License - See LICENSE file

## Support

For questions or issues:
- GitHub Issues: [repository]/issues
- Documentation: See `/docs` folder

## Roadmap

### Phase 2 (Current) - Prototype ✓
- Multi-agent RAG pipeline
- Sample documentation
- REST API
- Basic validation

### Phase 3 - Production
- Hybrid search (vector + BM25)
- Query caching
- Re-ranking with cross-encoders
- Multi-tenancy support
- Comprehensive monitoring

### Phase 4 - Advanced
- Multi-hop reasoning with memory
- Self-correction loops
- Query rewriting
- Personalized responses
- A/B testing framework
