# Contributing to Anavibe MCP A2A

Thank you for your interest in contributing to Anavibe! This document provides
guidelines and standards for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Security Considerations](#security-considerations)

---

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected
to uphold this code. Please be respectful, inclusive, and professional.

---

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/anavibe.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Submit a pull request

---

## Development Setup

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 15+
- Redis 7+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/djimit/anavibe.git
cd anavibe

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start development server
anavibe-server
```

---

## Code Standards

### Python Style Guide

We follow strict Python coding standards enforced by automated tools:

#### 1. Formatting
- **Line length**: Maximum 100 characters
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings
- **Imports**: Sorted by isort (standard library, third-party, local)

```python
# Correct import order
import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from anavibe.core.config import settings
from anavibe.models.agent import Agent
```

#### 2. Type Hints
All code must be fully typed:

```python
# Good - fully typed
def process_message(
    message: AgentMessage,
    sender_id: str,
    *,
    priority: int = 0,
) -> ProcessedMessage:
    ...

# Bad - missing types
def process_message(message, sender_id, priority=0):
    ...
```

#### 3. Docstrings
Use Google-style docstrings for public APIs:

```python
def register_agent(
    agent_name: str,
    capabilities: list[str],
) -> Agent:
    """Register a new agent in the system.

    Creates a new agent with the given name and capabilities.
    The agent will be assigned a unique ID and authentication token.

    Args:
        agent_name: Human-readable name for the agent.
        capabilities: List of capability identifiers.

    Returns:
        The newly created Agent instance.

    Raises:
        AgentExistsError: If an agent with this name already exists.
        ValidationError: If the input parameters are invalid.

    Example:
        >>> agent = register_agent("my-agent", ["chat", "code"])
        >>> print(agent.id)
        'agt_abc123'
    """
    ...
```

#### 4. Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `AgentManager` |
| Functions | snake_case | `process_message` |
| Variables | snake_case | `message_count` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Private | Leading underscore | `_internal_state` |
| Type aliases | PascalCase | `AgentId = str` |

#### 5. Error Handling

```python
# Good - specific exceptions with context
from anavibe.exceptions import AgentNotFoundError

async def get_agent(agent_id: str) -> Agent:
    agent = await agent_repository.find_by_id(agent_id)
    if agent is None:
        raise AgentNotFoundError(
            f"Agent not found",
            agent_id=agent_id,
        )
    return agent

# Bad - generic exceptions
async def get_agent(agent_id: str) -> Agent:
    agent = await agent_repository.find_by_id(agent_id)
    if agent is None:
        raise Exception("Not found")  # Don't do this
    return agent
```

#### 6. Async/Await

Use async consistently:

```python
# Good - async throughout
async def process_messages(agent_id: str) -> list[Message]:
    agent = await get_agent(agent_id)
    messages = await fetch_messages(agent)
    return await process_batch(messages)

# Bad - blocking in async context
async def process_messages(agent_id: str) -> list[Message]:
    agent = await get_agent(agent_id)
    messages = requests.get(...)  # Blocking call!
    return messages
```

### File Structure

```
src/anavibe/
├── __init__.py          # Package initialization
├── api/                 # API routes
│   ├── __init__.py
│   ├── v1/             # API version 1
│   │   ├── __init__.py
│   │   ├── agents.py
│   │   └── messages.py
│   └── deps.py         # Dependencies
├── core/               # Core functionality
│   ├── __init__.py
│   ├── config.py       # Configuration
│   └── security.py     # Security utilities
├── models/             # Pydantic models
│   ├── __init__.py
│   └── agent.py
├── services/           # Business logic
│   ├── __init__.py
│   └── agent_service.py
├── repositories/       # Data access
│   ├── __init__.py
│   └── agent_repository.py
├── middleware/         # Request middleware
│   ├── __init__.py
│   └── rate_limit.py
└── exceptions.py       # Custom exceptions
```

### Commit Messages

Follow the Conventional Commits specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, no code change)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding tests
- `chore`: Maintenance tasks
- `security`: Security-related changes

Examples:
```
feat(agents): add agent heartbeat monitoring

fix(auth): resolve JWT token expiration race condition

security(api): add rate limiting to authentication endpoints

Implements sliding window rate limiting with configurable
thresholds per endpoint.

Closes #123
```

---

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests
│   ├── test_services/
│   └── test_models/
├── integration/         # Integration tests
│   └── test_api/
└── e2e/                 # End-to-end tests
```

### Writing Tests

```python
import pytest
from httpx import AsyncClient

from anavibe.models.agent import Agent
from anavibe.services.agent_service import AgentService


class TestAgentService:
    """Tests for AgentService."""

    @pytest.fixture
    def agent_service(self, mock_repository: MockRepository) -> AgentService:
        return AgentService(repository=mock_repository)

    async def test_register_agent_success(
        self,
        agent_service: AgentService,
    ) -> None:
        """Should successfully register a new agent."""
        # Arrange
        name = "test-agent"
        capabilities = ["chat"]

        # Act
        agent = await agent_service.register(name, capabilities)

        # Assert
        assert agent.name == name
        assert agent.capabilities == capabilities
        assert agent.id is not None

    async def test_register_agent_duplicate_name_fails(
        self,
        agent_service: AgentService,
    ) -> None:
        """Should raise error when registering duplicate agent name."""
        # Arrange
        await agent_service.register("duplicate", [])

        # Act & Assert
        with pytest.raises(AgentExistsError):
            await agent_service.register("duplicate", [])
```

### Test Coverage

- Minimum 80% code coverage required
- 100% coverage for security-critical code
- All public APIs must have tests

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/anavibe --cov-report=html

# Run specific test file
pytest tests/unit/test_services/test_agent_service.py

# Run tests matching pattern
pytest -k "test_register"

# Run security tests only
pytest -m security
```

---

## Pull Request Process

### Before Submitting

1. [ ] Code follows style guidelines
2. [ ] All tests pass locally
3. [ ] New tests added for new functionality
4. [ ] Documentation updated if needed
5. [ ] No security vulnerabilities introduced
6. [ ] Commit messages follow convention

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe tests added/modified.

## Security Considerations
Note any security implications.

## Checklist
- [ ] Tests pass
- [ ] Linting passes
- [ ] Documentation updated
- [ ] No secrets committed
```

### Review Process

1. Automated checks must pass
2. At least one maintainer approval required
3. Security-sensitive changes require security review
4. Changes squashed before merge

---

## Security Considerations

### Before Contributing

- Read SECURITY.md thoroughly
- Never commit secrets or credentials
- Validate all user input
- Use parameterized queries
- Follow principle of least privilege

### Security Review Triggers

These changes require security team review:

- Authentication/authorization changes
- Cryptographic operations
- Input validation modifications
- New external dependencies
- API endpoint changes
- Database schema changes

---

## Questions?

- Open a discussion on GitHub
- Email: contributors@djimit.com

Thank you for contributing to Anavibe!
