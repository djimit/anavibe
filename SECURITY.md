# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of Anavibe MCP A2A seriously. If you discover a security
vulnerability, please report it responsibly.

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Email security concerns to: security@djimit.com
3. Include the following in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- Acknowledgment within 48 hours
- Regular updates on the progress
- Credit in the security advisory (if desired)

---

## Security Best Practices

This document outlines the security standards and guidelines for the Anavibe
MCP A2A project.

### 1. Authentication & Authorization

#### API Key Authentication
```python
# Always use constant-time comparison for API keys
import secrets

def verify_api_key(provided_key: str, stored_key: str) -> bool:
    return secrets.compare_digest(provided_key, stored_key)
```

#### JWT Token Handling
- Use strong secrets (minimum 256-bit)
- Implement token expiration (short-lived access tokens)
- Use refresh token rotation
- Store tokens securely (httpOnly cookies or secure storage)

```python
# JWT Configuration
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
```

#### Role-Based Access Control (RBAC)
- Implement principle of least privilege
- Define clear role hierarchies
- Audit permission changes

### 2. Input Validation & Sanitization

#### Always Validate Input
```python
from pydantic import BaseModel, Field, validator
import re

class AgentMessage(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    content: str = Field(..., max_length=65536)
    priority: int = Field(default=0, ge=0, le=10)

    @validator("content")
    def sanitize_content(cls, v: str) -> str:
        # Remove null bytes and control characters
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v)
```

#### SQL Injection Prevention
- Always use parameterized queries
- Use ORM (SQLAlchemy) with proper escaping
- Never concatenate user input into queries

```python
# GOOD - Parameterized query
result = await session.execute(
    select(Agent).where(Agent.id == agent_id)
)

# BAD - Never do this
# result = await session.execute(f"SELECT * FROM agents WHERE id = '{agent_id}'")
```

### 3. Cryptography

#### Password Hashing
```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Minimum 12 rounds
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

#### Encryption at Rest
- Use Fernet (AES-128-CBC) for symmetric encryption
- Store encryption keys in secure key management systems
- Rotate keys periodically

```python
from cryptography.fernet import Fernet

# Key generation (do once, store securely)
key = Fernet.generate_key()

# Encryption
cipher = Fernet(key)
encrypted = cipher.encrypt(b"sensitive data")

# Decryption
decrypted = cipher.decrypt(encrypted)
```

#### TLS/HTTPS
- Enforce HTTPS in production
- Use TLS 1.2 or higher
- Implement HSTS headers

### 4. Rate Limiting

Protect against abuse and DoS attacks:

```python
from anavibe.middleware.rate_limit import RateLimiter

# Configure rate limits per endpoint
rate_limiter = RateLimiter(
    default_limit=100,  # requests
    default_window=60,  # seconds
    endpoints={
        "/api/v1/auth/login": {"limit": 5, "window": 60},
        "/api/v1/agents/register": {"limit": 10, "window": 300},
    }
)
```

### 5. Logging & Monitoring

#### Secure Logging
- Never log sensitive data (passwords, tokens, PII)
- Use structured logging
- Implement log rotation

```python
import structlog

logger = structlog.get_logger()

# GOOD - Log action without sensitive data
logger.info("user_login", user_id=user.id, ip_address=request.client.host)

# BAD - Never log credentials
# logger.info("user_login", password=password)
```

#### Security Events to Monitor
- Failed authentication attempts
- Permission denied events
- Rate limit violations
- Unusual API patterns
- Agent registration/deregistration

### 6. Dependency Security

#### Regular Audits
```bash
# Check for vulnerabilities
pip-audit
safety check

# Update dependencies
pip install --upgrade -r requirements.txt
```

#### Dependency Pinning
- Pin exact versions in production
- Use hash verification
- Regular security updates

### 7. API Security

#### CORS Configuration
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trusted-domain.com"],  # Never use "*" in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

#### Security Headers
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

### 8. Agent-to-Agent Security

#### Message Authentication
- Sign all messages between agents
- Verify signatures before processing
- Use HMAC-SHA256 or Ed25519

```python
import hmac
import hashlib

def sign_message(message: bytes, secret: bytes) -> str:
    return hmac.new(secret, message, hashlib.sha256).hexdigest()

def verify_signature(message: bytes, signature: str, secret: bytes) -> bool:
    expected = sign_message(message, secret)
    return hmac.compare_digest(signature, expected)
```

#### Agent Identity Verification
- Require agent registration
- Implement certificate-based authentication
- Regular re-authentication

### 9. Data Protection

#### Sensitive Data Handling
- Minimize data collection
- Encrypt sensitive data at rest
- Implement data retention policies
- Secure data deletion

#### Environment Variables
- Never commit secrets to version control
- Use .env files (gitignored) or secret management
- Validate required environment variables at startup

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    secret_key: str  # Required - will fail if missing
    database_url: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 10. Error Handling

#### Safe Error Responses
```python
from fastapi import HTTPException

# GOOD - Generic error message
raise HTTPException(status_code=401, detail="Authentication failed")

# BAD - Reveals internal details
# raise HTTPException(status_code=401, detail=f"User {username} not found in database")
```

#### Exception Handling
- Catch and log all exceptions
- Return generic errors to clients
- Never expose stack traces in production

---

## Security Checklist

Before deploying to production, verify:

- [ ] All secrets are stored securely (not in code)
- [ ] HTTPS is enforced
- [ ] Rate limiting is configured
- [ ] Input validation is implemented
- [ ] SQL injection prevention verified
- [ ] Authentication tokens are short-lived
- [ ] CORS is properly configured
- [ ] Security headers are set
- [ ] Logging excludes sensitive data
- [ ] Dependencies are up to date
- [ ] Static analysis (bandit) passes
- [ ] Penetration testing completed

---

## Security Tools

### Static Analysis
```bash
# Run security linter
bandit -r src/ -c pyproject.toml

# Check dependencies
safety check
pip-audit
```

### Dynamic Testing
- Use OWASP ZAP for API testing
- Implement fuzz testing for inputs
- Regular penetration testing

---

## Incident Response

1. **Identify** - Detect and confirm the incident
2. **Contain** - Limit the damage
3. **Eradicate** - Remove the threat
4. **Recover** - Restore normal operations
5. **Lessons Learned** - Document and improve

Contact: security@djimit.com
