# System Architecture

## Overview
Our SaaS platform (CloudSync) is a real-time data synchronization service built on microservices architecture.

## Core Components

### API Gateway
- **Technology**: Kong on AWS EC2
- **Responsibilities**: 
  - Request routing to appropriate services
  - Rate limiting (100 req/min per user by default)
  - SSL termination
  - Authentication header validation

### Auth Service
- **Technology**: Node.js + Express
- **Features**:
  - JWT token generation and validation
  - OAuth2 integration (Google, GitHub)
  - Role-based access control (RBAC)
  - Token refresh mechanism

### Sync Engine
- **Technology**: Python 3.11 + Celery
- **Functions**:
  - Real-time data change detection
  - Conflict resolution strategies
  - Event-driven architecture using Redis pub/sub
  - Retry logic with exponential backoff

### Database Layer
- **Primary**: PostgreSQL 14 (RDS)
  - Stores user data, metadata, configuration
  - Automated backups every 6 hours
  - Multi-AZ deployment for high availability
- **Cache**: Redis (ElastiCache)
  - Session storage
  - Job queues for Celery
  - Rate limiting counters

### Storage
- **AWS S3**: File attachments and exports
  - Encrypted at rest (SSE-S3)
  - Lifecycle policies: Move to Glacier after 90 days
  - CORS configured for direct browser uploads

## Tech Stack Summary

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python | 3.11 |
| API Framework | FastAPI | 0.104+ |
| Frontend | React | 18.x |
| Frontend Lang | TypeScript | 5.x |
| Database | PostgreSQL | 14 |
| Cache | Redis | 7.x |
| Message Queue | Redis + Celery | Latest |
| Infrastructure | AWS ECS | Fargate |

## Data Flow

1. Client makes request → API Gateway
2. Gateway validates JWT → Auth Service
3. Auth Service returns user context
4. Request routed to appropriate microservice
5. Service reads/writes to PostgreSQL
6. Sync Engine detects changes via triggers
7. Celery workers process background jobs
8. Response returned through Gateway

## Security

- All internal communication over TLS 1.3
- Database connections use IAM authentication
- API keys rotated every 90 days
- Secrets managed via AWS Secrets Manager