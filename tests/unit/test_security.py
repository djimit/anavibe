"""Unit tests for security module."""

import pytest

from anavibe.core.security import SecurityManager, pwd_context


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_returns_hash(self) -> None:
        """Should return a bcrypt hash."""
        password = "secure_password_123"
        hashed = SecurityManager.hash_password(password)

        assert hashed is not None
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self) -> None:
        """Should verify correct password."""
        password = "secure_password_123"
        hashed = SecurityManager.hash_password(password)

        assert SecurityManager.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """Should reject incorrect password."""
        password = "secure_password_123"
        hashed = SecurityManager.hash_password(password)

        assert SecurityManager.verify_password("wrong_password", hashed) is False

    def test_hash_password_unique_salts(self) -> None:
        """Should generate unique hashes for same password."""
        password = "same_password"
        hash1 = SecurityManager.hash_password(password)
        hash2 = SecurityManager.hash_password(password)

        assert hash1 != hash2  # Different salts


class TestJWTTokens:
    """Tests for JWT token functionality."""

    def test_create_access_token(self, security_manager: SecurityManager) -> None:
        """Should create valid access token."""
        token = security_manager.create_access_token(
            subject="test-user",
            additional_claims={"role": "admin"},
        )

        assert token is not None
        assert len(token) > 0

    def test_verify_access_token(self, security_manager: SecurityManager) -> None:
        """Should verify and decode access token."""
        subject = "test-user-123"
        token = security_manager.create_access_token(subject=subject)

        payload = security_manager.verify_token(token)

        assert payload["sub"] == subject
        assert payload["type"] == "access"

    def test_create_refresh_token(self, security_manager: SecurityManager) -> None:
        """Should create valid refresh token."""
        token = security_manager.create_refresh_token(subject="test-user")

        payload = security_manager.verify_token(token, token_type="refresh")

        assert payload["type"] == "refresh"
        assert "jti" in payload  # Should have unique ID

    def test_get_token_subject(self, security_manager: SecurityManager) -> None:
        """Should extract subject from token."""
        subject = "agent-abc-123"
        token = security_manager.create_access_token(subject=subject)

        extracted = security_manager.get_token_subject(token)

        assert extracted == subject

    def test_invalid_token_raises_error(self, security_manager: SecurityManager) -> None:
        """Should raise error for invalid token."""
        from anavibe.exceptions import InvalidTokenError

        with pytest.raises(InvalidTokenError):
            security_manager.verify_token("invalid.token.here")

    def test_wrong_token_type_raises_error(self, security_manager: SecurityManager) -> None:
        """Should raise error when token type doesn't match."""
        from anavibe.exceptions import InvalidTokenError

        access_token = security_manager.create_access_token(subject="user")

        with pytest.raises(InvalidTokenError):
            security_manager.verify_token(access_token, token_type="refresh")


class TestAPIKeys:
    """Tests for API key functionality."""

    def test_generate_api_key_format(self) -> None:
        """Should generate API key with correct format."""
        key = SecurityManager.generate_api_key()

        assert key.startswith("av_")
        assert len(key) > 10

    def test_generate_api_key_custom_prefix(self) -> None:
        """Should use custom prefix."""
        key = SecurityManager.generate_api_key(prefix="test")

        assert key.startswith("test_")

    def test_hash_api_key_consistent(self) -> None:
        """Should produce consistent hash for same key."""
        key = "av_test_key_123"
        hash1 = SecurityManager.hash_api_key(key)
        hash2 = SecurityManager.hash_api_key(key)

        assert hash1 == hash2

    def test_verify_api_key_correct(self) -> None:
        """Should verify correct API key."""
        key = SecurityManager.generate_api_key()
        hashed = SecurityManager.hash_api_key(key)

        assert SecurityManager.verify_api_key(key, hashed) is True

    def test_verify_api_key_incorrect(self) -> None:
        """Should reject incorrect API key."""
        key = SecurityManager.generate_api_key()
        hashed = SecurityManager.hash_api_key(key)

        assert SecurityManager.verify_api_key("av_wrong_key", hashed) is False


class TestMessageSigning:
    """Tests for message signing functionality."""

    def test_sign_message(self, security_manager: SecurityManager) -> None:
        """Should sign message."""
        message = b"Hello, World!"
        signature = security_manager.sign_message(message)

        assert signature is not None
        assert len(signature) == 64  # SHA-256 hex digest

    def test_verify_signature_valid(self, security_manager: SecurityManager) -> None:
        """Should verify valid signature."""
        message = b"Test message"
        signature = security_manager.sign_message(message)

        assert security_manager.verify_signature(message, signature) is True

    def test_verify_signature_invalid(self, security_manager: SecurityManager) -> None:
        """Should reject invalid signature."""
        message = b"Test message"
        signature = security_manager.sign_message(message)

        assert security_manager.verify_signature(b"Different message", signature) is False


class TestSecureTokenGeneration:
    """Tests for secure token generation."""

    def test_generate_secure_token_default_length(self) -> None:
        """Should generate token with default length."""
        token = SecurityManager.generate_secure_token()

        assert token is not None
        assert len(token) > 0

    def test_generate_secure_token_custom_length(self) -> None:
        """Should generate token with custom length."""
        token1 = SecurityManager.generate_secure_token(length=16)
        token2 = SecurityManager.generate_secure_token(length=64)

        # URL-safe base64 encoding: ~4/3 * bytes
        assert len(token1) < len(token2)

    def test_generate_secure_token_unique(self) -> None:
        """Should generate unique tokens."""
        tokens = [SecurityManager.generate_secure_token() for _ in range(100)]

        assert len(set(tokens)) == 100


class TestConstantTimeCompare:
    """Tests for constant-time comparison."""

    def test_constant_time_compare_equal(self) -> None:
        """Should return True for equal strings."""
        assert SecurityManager.constant_time_compare("secret", "secret") is True

    def test_constant_time_compare_not_equal(self) -> None:
        """Should return False for different strings."""
        assert SecurityManager.constant_time_compare("secret", "different") is False

    def test_constant_time_compare_empty(self) -> None:
        """Should handle empty strings."""
        assert SecurityManager.constant_time_compare("", "") is True
        assert SecurityManager.constant_time_compare("a", "") is False
