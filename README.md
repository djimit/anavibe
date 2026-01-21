# Anavibe MCP A2A

**Model Context Protocol Agent-to-Agent Communication Framework**

[![CI](https://github.com/djimit/anavibe/actions/workflows/ci.yml/badge.svg)](https://github.com/djimit/anavibe/actions/workflows/ci.yml)
[![Security](https://github.com/djimit/anavibe/actions/workflows/security.yml/badge.svg)](https://github.com/djimit/anavibe/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/djimit/anavibe/branch/main/graph/badge.svg)](https://codecov.io/gh/djimit/anavibe)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Anavibe is a secure, high-performance framework for agent-to-agent communication built on the Model Context Protocol (MCP). It enables AI agents to discover, authenticate, and communicate with each other through a standardized API.

## Features

- **Agent Registration & Discovery** - Register agents with capabilities and discover other agents
- **Secure Authentication** - JWT-based authentication with API key support
- **Message Queue** - Reliable message delivery between agents with priority support
- **Rate Limiting** - Protect against abuse with configurable rate limits
- **End-to-End Encryption** - Optional Fernet encryption for A2A messages
- **Structured Logging** - JSON logging with correlation IDs for traceability
- **Security First** - OWASP best practices, security headers, input validation
- **Type Safety** - Full type hints with Pydantic v2 models
- **Async Native** - Built on FastAPI with async/await throughout

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Installation

```bash
# Clone the repository
git clone https://github.com/djimit/anavibe.git
cd anavibe

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file and configure
cp .env.example .env
# Edit .env with your settings

# Generate a secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Using Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Running the Server

```bash
# Development mode with auto-reload
anavibe serve --reload

# Production mode
anavibe serve --workers 4

# Or using uvicorn directly
uvicorn anavibe.server:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. API documentation is at `http://localhost:8000/docs` (development only).

## API Overview

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### Register an Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-agent",
    "description": "My AI agent",
    "capabilities": ["chat", "code"]
  }'
```

Response includes an API key (shown only once):
```json
{
  "agent": {
    "id": "agt_abc123...",
    "name": "my-agent",
    "capabilities": ["chat", "code"]
  },
  "api_key": "av_xyz789..."
}
```

### Authenticate

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agt_abc123",
    "api_key": "av_xyz789..."
  }'
```

### Send a Message

```bash
curl -X POST http://localhost:8000/api/v1/messages \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_id": "agt_recipient",
    "content": "Hello, agent!",
    "priority": 5
  }'
```

### List Messages

```bash
curl http://localhost:8000/api/v1/messages \
  -H "Authorization: Bearer <access_token>"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Anavibe MCP A2A                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   FastAPI   │  │ Middleware  │  │    Security Layer   │  │
│  │   Router    │  │   Stack     │  │  - Authentication   │  │
│  │             │  │  - CORS     │  │  - Authorization    │  │
│  │  /agents    │  │  - Rate     │  │  - Encryption       │  │
│  │  /messages  │  │    Limit    │  │  - Validation       │  │
│  │  /auth      │  │  - Headers  │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Service Layer                        ││
│  │  - Agent Management    - Message Routing                ││
│  │  - Authentication      - Queue Management               ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐           ┌─────────────────────────┐  │
│  │   PostgreSQL    │           │         Redis           │  │
│  │  - Agents       │           │  - Rate Limiting        │  │
│  │  - Messages     │           │  - Session Cache        │  │
│  │  - API Keys     │           │  - Message Queue        │  │
│  └─────────────────┘           └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Configuration is managed via environment variables. See `.env.example` for all options.

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/staging/production) | development |
| `SECRET_KEY` | Secret key for JWT signing (min 32 chars) | **required** |
| `DATABASE_URL` | PostgreSQL connection URL | **required** |
| `REDIS_URL` | Redis connection URL | redis://localhost:6379/0 |
| `RATE_LIMIT_ENABLED` | Enable rate limiting | true |
| `A2A_ENCRYPTION_ENABLED` | Enable message encryption | true |

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run linting
ruff check src/ tests/

# Run type checking
mypy src/

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/anavibe --cov-report=html
```

### Project Structure

```
anavibe/
├── src/anavibe/
│   ├── api/              # API routes
│   │   └── v1/           # API version 1
│   ├── core/             # Core functionality
│   │   ├── config.py     # Configuration
│   │   ├── security.py   # Security utilities
│   │   └── logging.py    # Logging setup
│   ├── middleware/       # Request middleware
│   ├── models/           # Pydantic models
│   ├── services/         # Business logic
│   ├── repositories/     # Data access
│   ├── exceptions.py     # Custom exceptions
│   ├── server.py         # FastAPI application
│   └── cli.py            # CLI interface
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── .github/workflows/    # CI/CD pipelines
├── pyproject.toml        # Project configuration
└── docker-compose.yml    # Docker services
```

### CLI Commands

```bash
# Start server
anavibe serve [--host HOST] [--port PORT] [--workers N] [--reload]

# Generate secrets
anavibe generate secret-key      # Generate JWT secret key
anavibe generate api-key         # Generate API key
anavibe generate encryption-key  # Generate Fernet encryption key

# Health check
anavibe health [--url URL]
```

## Security

Security is a core focus of Anavibe. See [SECURITY.md](SECURITY.md) for:

- Security best practices
- Vulnerability reporting
- Authentication & authorization guidelines
- Input validation requirements
- Cryptography standards

### Security Features

- **Authentication**: JWT tokens with short expiration, refresh token rotation
- **Authorization**: Role-based access control, capability-based permissions
- **Encryption**: Fernet (AES-128-CBC) for A2A message encryption
- **Rate Limiting**: Sliding window algorithm with Redis backend
- **Input Validation**: Pydantic models with strict validation
- **Security Headers**: HSTS, CSP, X-Frame-Options, etc.
- **Audit Logging**: Structured logs with correlation IDs

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code style guidelines
- Testing requirements
- Pull request process
- Security considerations

## Roadmap

### Enhanced Features (Future)

- [ ] **WebSocket Support** - Real-time bidirectional communication
- [ ] **Agent Groups** - Organize agents into groups for broadcasting
- [ ] **Message Persistence** - Long-term message storage and retrieval
- [ ] **Agent Discovery** - Service discovery for automatic agent finding
- [ ] **Metrics & Monitoring** - Prometheus metrics, distributed tracing
- [ ] **Multi-tenancy** - Workspace isolation for enterprise deployments
- [ ] **Plugin System** - Extensible architecture for custom capabilities
- [ ] **GraphQL API** - Alternative API for complex queries
- [ ] **Event Streaming** - Kafka/NATS integration for high-throughput
- [ ] **Admin Dashboard** - Web UI for monitoring and management

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Dutch Dim** - [d.landman@djimit.com](mailto:d.landman@djimit.com)

---

Built with Python and FastAPI
