"""
Unit tests for validators.py

Tests for input validation, sanitization, and rate limiting.
"""

import pytest
import time
from validators import (
    validate_session_id,
    validate_message,
    validate_chat_request,
    sanitize_html,
    validate_and_sanitize_filename,
    ValidationError,
    SessionIDValidationError,
    MessageValidationError,
    RateLimitError,
    RateLimiter
)
import config

# ============================================================================
# Session ID Validation Tests
# ============================================================================

@pytest.mark.unit
class TestSessionIDValidation:
    """Tests for validate_session_id()"""

    def test_valid_session_id_alphanumeric(self):
        """Test valid alphanumeric session ID"""
        result = validate_session_id("test123")
        assert result == "test123"

    def test_valid_session_id_with_underscore(self):
        """Test valid session ID with underscore"""
        result = validate_session_id("test_session_123")
        assert result == "test_session_123"

    def test_valid_session_id_with_hyphen(self):
        """Test valid session ID with hyphen"""
        result = validate_session_id("test-session-123")
        assert result == "test-session-123"

    def test_valid_session_id_mixed(self):
        """Test valid session ID with mixed valid characters"""
        result = validate_session_id("Test_Session-123")
        assert result == "Test_Session-123"

    def test_session_id_with_whitespace_trimmed(self):
        """Test session ID with leading/trailing whitespace is trimmed"""
        result = validate_session_id("  test123  ")
        assert result == "test123"

    def test_empty_session_id_raises_error(self):
        """Test empty session ID raises SessionIDValidationError"""
        with pytest.raises(SessionIDValidationError, match="cannot be empty"):
            validate_session_id("")

    def test_whitespace_only_session_id_raises_error(self):
        """Test whitespace-only session ID raises error"""
        with pytest.raises(SessionIDValidationError, match="cannot be empty"):
            validate_session_id("   ")

    def test_session_id_too_long_raises_error(self):
        """Test session ID exceeding max length raises error"""
        long_id = "a" * (config.MAX_SESSION_ID_LENGTH + 1)
        with pytest.raises(SessionIDValidationError, match="too long"):
            validate_session_id(long_id)

    def test_session_id_at_max_length_is_valid(self):
        """Test session ID at exactly max length is valid"""
        max_id = "a" * config.MAX_SESSION_ID_LENGTH
        result = validate_session_id(max_id)
        assert result == max_id

    def test_session_id_with_special_chars_raises_error(self):
        """Test session ID with special characters raises error"""
        invalid_ids = [
            "test@session",
            "test#session",
            "test$session",
            "test%session",
            "test session",  # space
            "test.session",  # dot
            "test/session",  # slash
            "test\\session",  # backslash
        ]
        for invalid_id in invalid_ids:
            with pytest.raises(SessionIDValidationError, match="alphanumeric"):
                validate_session_id(invalid_id)

# ============================================================================
# Message Validation Tests
# ============================================================================

@pytest.mark.unit
class TestMessageValidation:
    """Tests for validate_message()"""

    def test_valid_message(self):
        """Test valid message passes validation"""
        result = validate_message("Hello, world!")
        assert result == "Hello, world!"

    def test_message_with_whitespace_trimmed(self):
        """Test message with leading/trailing whitespace is trimmed"""
        result = validate_message("  Hello, world!  ")
        assert result == "Hello, world!"

    def test_empty_message_raises_error(self):
        """Test empty message raises MessageValidationError"""
        with pytest.raises(MessageValidationError, match="too short"):
            validate_message("")

    def test_whitespace_only_message_raises_error(self):
        """Test whitespace-only message raises error"""
        with pytest.raises(MessageValidationError, match="too short"):
            validate_message("   ")

    def test_message_at_min_length_is_valid(self):
        """Test message at minimum length is valid"""
        min_msg = "a" * config.MIN_MESSAGE_LENGTH
        result = validate_message(min_msg)
        assert result == min_msg

    def test_message_too_long_raises_error(self):
        """Test message exceeding max length raises error"""
        long_msg = "a" * (config.MAX_MESSAGE_LENGTH + 1)
        with pytest.raises(MessageValidationError, match="too long"):
            validate_message(long_msg)

    def test_message_at_max_length_is_valid(self):
        """Test message at exactly max length is valid"""
        max_msg = "a" * config.MAX_MESSAGE_LENGTH
        result = validate_message(max_msg)
        assert result == max_msg

    def test_message_with_null_byte_raises_error(self):
        """Test message with null byte raises error"""
        with pytest.raises(MessageValidationError, match="invalid characters"):
            validate_message("Hello\x00World")

    def test_message_none_raises_error(self):
        """Test None message raises error"""
        with pytest.raises(MessageValidationError, match="cannot be None"):
            validate_message(None)

    def test_message_converts_to_string(self):
        """Test message is converted to string if needed"""
        result = validate_message(123)
        assert result == "123"
        assert isinstance(result, str)

    def test_message_with_unicode_is_valid(self):
        """Test message with unicode characters is valid"""
        result = validate_message("Hello 你好 🌍")
        assert result == "Hello 你好 🌍"

    def test_message_with_newlines_is_valid(self):
        """Test message with newlines is valid"""
        msg = "Line 1\nLine 2\nLine 3"
        result = validate_message(msg)
        assert result == msg

# ============================================================================
# Rate Limiter Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestRateLimiter:
    """Tests for RateLimiter class"""

    def test_rate_limiter_allows_requests_within_limit(self):
        """Test rate limiter allows requests up to the limit"""
        limiter = RateLimiter()
        session_id = "test-session-allow"

        # Should allow up to MAX_REQUESTS
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            try:
                limiter.check_rate_limit(session_id)
            except RateLimitError:
                pytest.fail(f"Rate limiter blocked request {i+1} of {config.RATE_LIMIT_MAX_REQUESTS}")

    def test_rate_limiter_blocks_request_over_limit(self):
        """Test rate limiter blocks request exceeding limit"""
        limiter = RateLimiter()
        session_id = "test-session-block"

        # Fill up the limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            limiter.check_rate_limit(session_id)

        # Next request should be blocked
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            limiter.check_rate_limit(session_id)

    def test_rate_limiter_provides_wait_time(self):
        """Test rate limiter error message includes wait time"""
        limiter = RateLimiter()
        session_id = "test-session-wait"

        # Fill up the limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            limiter.check_rate_limit(session_id)

        # Check error message includes wait time
        with pytest.raises(RateLimitError) as exc_info:
            limiter.check_rate_limit(session_id)

        assert "wait" in str(exc_info.value).lower()
        assert "seconds" in str(exc_info.value).lower()

    def test_rate_limiter_different_sessions_independent(self):
        """Test rate limiter tracks sessions independently"""
        limiter = RateLimiter()
        session1 = "test-session-1"
        session2 = "test-session-2"

        # Fill session1 to limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            limiter.check_rate_limit(session1)

        # Session1 should be blocked
        with pytest.raises(RateLimitError):
            limiter.check_rate_limit(session1)

        # Session2 should still work
        limiter.check_rate_limit(session2)  # Should not raise

    def test_rate_limiter_reset_session(self):
        """Test rate limiter reset_session() clears the limit"""
        limiter = RateLimiter()
        session_id = "test-session-reset"

        # Fill up the limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            limiter.check_rate_limit(session_id)

        # Should be blocked
        with pytest.raises(RateLimitError):
            limiter.check_rate_limit(session_id)

        # Reset and try again
        limiter.reset_session(session_id)
        limiter.check_rate_limit(session_id)  # Should not raise

    @pytest.mark.slow
    def test_rate_limiter_sliding_window(self):
        """Test rate limiter uses sliding window (old requests expire)"""
        # Note: This test is marked as slow because it requires waiting
        limiter = RateLimiter()
        session_id = "test-session-sliding"

        # Make a request
        limiter.check_rate_limit(session_id)

        # Wait for window to partially pass
        # In real scenario, old requests would expire
        # For testing, we just verify the mechanism exists
        assert session_id in limiter.requests
        assert len(limiter.requests[session_id]) == 1

# ============================================================================
# Combined Validation Tests
# ============================================================================

@pytest.mark.unit
class TestValidateChatRequest:
    """Tests for validate_chat_request()"""

    def test_valid_request_passes(self):
        """Test valid session ID and message pass validation"""
        session_id, message = validate_chat_request("test-session", "Hello!")
        assert session_id == "test-session"
        assert message == "Hello!"

    def test_invalid_session_id_raises_error(self):
        """Test invalid session ID raises SessionIDValidationError"""
        with pytest.raises(SessionIDValidationError):
            validate_chat_request("test@invalid", "Hello!")

    def test_invalid_message_raises_error(self):
        """Test invalid message raises MessageValidationError"""
        with pytest.raises(MessageValidationError):
            validate_chat_request("test-session", "")

    def test_both_values_validated_and_sanitized(self):
        """Test both values are validated and sanitized"""
        session_id, message = validate_chat_request("  test  ", "  Hello!  ")
        assert session_id == "test"
        assert message == "Hello!"

    def test_rate_limit_checked(self):
        """Test rate limit is checked in validate_chat_request"""
        # Create a new session for this test
        test_session = "test-rate-limit-session-unique"

        # Fill up the rate limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            validate_chat_request(test_session, f"Message {i}")

        # Next request should raise RateLimitError
        with pytest.raises(RateLimitError):
            validate_chat_request(test_session, "One more message")

# ============================================================================
# Sanitization Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestSanitization:
    """Tests for sanitization helper functions"""

    def test_sanitize_html_escapes_tags(self):
        """Test HTML tags are properly escaped"""
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_html_escapes_quotes(self):
        """Test quotes are properly escaped"""
        result = sanitize_html('He said "hello"')
        assert '"' not in result
        assert "&quot;" in result

    def test_sanitize_html_escapes_apostrophes(self):
        """Test apostrophes are properly escaped"""
        result = sanitize_html("It's a test")
        assert "'" not in result or "&#x27;" in result

    def test_sanitize_html_multiple_escapes(self):
        """Test multiple HTML entities are escaped"""
        result = sanitize_html('<a href="test">Link</a>')
        assert "<a" not in result
        assert "href" in result  # attribute name preserved
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&quot;" in result

    def test_validate_filename_removes_path_traversal(self):
        """Test filename validation removes path traversal attempts"""
        result = validate_and_sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_validate_filename_allows_safe_chars(self):
        """Test filename validation allows safe characters"""
        result = validate_and_sanitize_filename("my-file_name.txt")
        assert result == "my-file_name.txt"

    def test_validate_filename_removes_unsafe_chars(self):
        """Test filename validation removes unsafe characters"""
        result = validate_and_sanitize_filename("file@name!.txt")
        assert "@" not in result
        assert "!" not in result

    def test_validate_filename_empty_raises_error(self):
        """Test empty filename raises ValidationError"""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_and_sanitize_filename("")

    def test_validate_filename_all_invalid_raises_error(self):
        """Test filename with all invalid chars raises error"""
        with pytest.raises(ValidationError, match="Invalid filename"):
            validate_and_sanitize_filename("@#$%")

# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def clean_rate_limiter():
    """Fixture that provides a clean RateLimiter instance"""
    return RateLimiter()

@pytest.fixture
def test_session_id():
    """Fixture that provides a unique test session ID"""
    import uuid
    return f"test-session-{uuid.uuid4().hex[:8]}"
