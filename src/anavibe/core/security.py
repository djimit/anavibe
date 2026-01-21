"""Security utilities for authentication, authorization, and cryptography.

This module provides secure implementations for:
- Password hashing with bcrypt
- JWT token generation and validation
- API key management
- Message signing and verification
- Encryption/decryption for A2A communication
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from anavibe.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    TokenExpiredError,
)


if TYPE_CHECKING:
    from anavibe.core.config import Settings


# Password hashing context with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Minimum 12 rounds for security
)


class SecurityManager:
    """Centralized security operations manager.

    Provides methods for:
    - Password hashing and verification
    - JWT token management
    - API key generation and validation
    - Message signing
    - A2A message encryption
    """

    def __init__(self, settings: "Settings") -> None:
        """Initialize the security manager.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        self._fernet: Fernet | None = None

        # Initialize Fernet cipher if encryption key is provided
        if settings.a2a_encryption_enabled and settings.a2a_encryption_key:
            self._fernet = Fernet(settings.a2a_encryption_key.encode())

    # =========================================================================
    # Password Operations
    # =========================================================================

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password.

        Returns:
            Hashed password string.
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            plain_password: Plain text password to verify.
            hashed_password: Stored password hash.

        Returns:
            True if password matches, False otherwise.
        """
        return pwd_context.verify(plain_password, hashed_password)

    # =========================================================================
    # JWT Token Operations
    # =========================================================================

    def create_access_token(
        self,
        subject: str,
        *,
        additional_claims: dict[str, Any] | None = None,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token.

        Args:
            subject: Token subject (usually user/agent ID).
            additional_claims: Extra claims to include in token.
            expires_delta: Custom expiration time.

        Returns:
            Encoded JWT token string.
        """
        if expires_delta is None:
            expires_delta = timedelta(
                minutes=self._settings.jwt_access_token_expire_minutes
            )

        expire = datetime.now(UTC) + expires_delta
        claims = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": "access",
        }

        if additional_claims:
            claims.update(additional_claims)

        return jwt.encode(
            claims,
            self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def create_refresh_token(
        self,
        subject: str,
        *,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT refresh token.

        Args:
            subject: Token subject (usually user/agent ID).
            expires_delta: Custom expiration time.

        Returns:
            Encoded JWT refresh token string.
        """
        if expires_delta is None:
            expires_delta = timedelta(
                days=self._settings.jwt_refresh_token_expire_days
            )

        expire = datetime.now(UTC) + expires_delta
        claims = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": "refresh",
            "jti": secrets.token_urlsafe(16),  # Unique token ID
        }

        return jwt.encode(
            claims,
            self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def verify_token(
        self,
        token: str,
        *,
        token_type: str = "access",
    ) -> dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string to verify.
            token_type: Expected token type ('access' or 'refresh').

        Returns:
            Decoded token payload.

        Raises:
            TokenExpiredError: If token has expired.
            InvalidTokenError: If token is invalid.
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise InvalidTokenError(
                    "Invalid token type",
                    details={"expected": token_type},
                )

            return payload

        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError() from e
        except JWTError as e:
            raise InvalidTokenError() from e

    def get_token_subject(self, token: str) -> str:
        """Extract subject from a token.

        Args:
            token: JWT token string.

        Returns:
            Token subject (user/agent ID).

        Raises:
            InvalidTokenError: If token is invalid or missing subject.
        """
        payload = self.verify_token(token)
        subject = payload.get("sub")
        if not subject:
            raise InvalidTokenError("Token missing subject")
        return subject

    # =========================================================================
    # API Key Operations
    # =========================================================================

    @staticmethod
    def generate_api_key(prefix: str = "av") -> str:
        """Generate a secure API key.

        Format: {prefix}_{random_32_bytes_hex}

        Args:
            prefix: Key prefix for identification.

        Returns:
            Generated API key string.
        """
        random_bytes = secrets.token_hex(32)
        return f"{prefix}_{random_bytes}"

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage.

        Uses SHA-256 for fast lookups while maintaining security.

        Args:
            api_key: Plain API key.

        Returns:
            Hashed API key.
        """
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def verify_api_key(provided_key: str, stored_hash: str) -> bool:
        """Verify an API key against stored hash.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            provided_key: API key provided by client.
            stored_hash: Stored hash to verify against.

        Returns:
            True if key is valid, False otherwise.
        """
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        return secrets.compare_digest(provided_hash, stored_hash)

    # =========================================================================
    # Message Signing Operations
    # =========================================================================

    def sign_message(self, message: bytes) -> str:
        """Sign a message using HMAC-SHA256.

        Args:
            message: Message bytes to sign.

        Returns:
            Hexadecimal signature string.
        """
        return hmac.new(
            self._settings.secret_key.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self, message: bytes, signature: str) -> bool:
        """Verify a message signature.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            message: Original message bytes.
            signature: Signature to verify.

        Returns:
            True if signature is valid, False otherwise.
        """
        expected = self.sign_message(message)
        return hmac.compare_digest(signature, expected)

    # =========================================================================
    # A2A Encryption Operations
    # =========================================================================

    def encrypt_message(self, plaintext: bytes) -> bytes:
        """Encrypt a message for A2A communication.

        Uses Fernet symmetric encryption (AES-128-CBC with HMAC).

        Args:
            plaintext: Message bytes to encrypt.

        Returns:
            Encrypted message bytes.

        Raises:
            AuthenticationError: If encryption is not configured.
        """
        if not self._fernet:
            raise AuthenticationError(
                "A2A encryption not configured",
                details={"reason": "Missing encryption key"},
            )
        return self._fernet.encrypt(plaintext)

    def decrypt_message(self, ciphertext: bytes) -> bytes:
        """Decrypt an A2A message.

        Args:
            ciphertext: Encrypted message bytes.

        Returns:
            Decrypted plaintext bytes.

        Raises:
            AuthenticationError: If decryption fails or not configured.
        """
        if not self._fernet:
            raise AuthenticationError(
                "A2A encryption not configured",
                details={"reason": "Missing encryption key"},
            )
        try:
            return self._fernet.decrypt(ciphertext)
        except InvalidToken as e:
            raise AuthenticationError(
                "Failed to decrypt message",
                details={"reason": "Invalid or corrupted ciphertext"},
            ) from e

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token.

        Args:
            length: Token length in bytes.

        Returns:
            URL-safe base64 encoded token.
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        """Constant-time string comparison.

        Prevents timing attacks when comparing sensitive values.

        Args:
            a: First string.
            b: Second string.

        Returns:
            True if strings are equal, False otherwise.
        """
        return secrets.compare_digest(a, b)
