"""
PromptPane Input Validation

This module contains input validation and sanitization functions:
- Session ID validation
- Message content validation
- Rate limiting
- Security checks
"""

import re
import time
from typing import Optional
from collections import defaultdict, deque

# Import configuration
import config

# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationError(Exception):
    """Base exception for validation errors"""
    pass

class SessionIDValidationError(ValidationError):
    """Raised when session ID validation fails"""
    pass

class MessageValidationError(ValidationError):
    """Raised when message validation fails"""
    pass

class RateLimitError(ValidationError):
    """Raised when rate limit is exceeded"""
    pass

# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """
    Simple rate limiter using sliding window approach.
    Tracks requests per session within a time window.
    """

    def __init__(self):
        # Store deque of timestamps per session
        self.requests: dict[str, deque[float]] = defaultdict(lambda: deque())

    def check_rate_limit(self, session_id: str) -> None:
        """
        Check if session has exceeded rate limit.

        Args:
            session_id: Session identifier to check

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        if not config.ENABLE_RATE_LIMITING:
            return

        current_time = time.time()
        window_start = current_time - config.RATE_LIMIT_WINDOW_SECONDS

        # Get request history for this session
        request_times = self.requests[session_id]

        # Remove old requests outside the time window
        while request_times and request_times[0] < window_start:
            request_times.popleft()

        # Check if limit exceeded
        if len(request_times) >= config.RATE_LIMIT_MAX_REQUESTS:
            oldest_request = request_times[0]
            wait_time = int(config.RATE_LIMIT_WINDOW_SECONDS - (current_time - oldest_request))
            raise RateLimitError(
                f"Rate limit exceeded. Maximum {config.RATE_LIMIT_MAX_REQUESTS} requests "
                f"per {config.RATE_LIMIT_WINDOW_SECONDS} seconds. "
                f"Please wait {wait_time} seconds before trying again."
            )

        # Add current request
        request_times.append(current_time)

    def reset_session(self, session_id: str) -> None:
        """
        Reset rate limit for a session.

        Args:
            session_id: Session identifier to reset
        """
        if session_id in self.requests:
            del self.requests[session_id]

# Global rate limiter instance
rate_limiter = RateLimiter()

# ============================================================================
# Session ID Validation
# ============================================================================

def validate_session_id(session_id: str) -> str:
    """
    Validate and sanitize session ID.

    Args:
        session_id: Session identifier to validate

    Returns:
        Validated and sanitized session ID

    Raises:
        SessionIDValidationError: If validation fails
    """
    # Check if empty
    if not session_id or not session_id.strip():
        raise SessionIDValidationError("Session ID cannot be empty")

    # Trim whitespace
    session_id = session_id.strip()

    # Check length
    if len(session_id) > config.MAX_SESSION_ID_LENGTH:
        raise SessionIDValidationError(
            f"Session ID too long. Maximum length is {config.MAX_SESSION_ID_LENGTH} characters"
        )

    # Check format (alphanumeric, underscore, hyphen only)
    if not re.match(config.SESSION_ID_PATTERN, session_id):
        raise SessionIDValidationError(
            "Session ID can only contain alphanumeric characters, underscores, and hyphens"
        )

    return session_id

# ============================================================================
# Message Content Validation
# ============================================================================

def validate_message(message: str) -> str:
    """
    Validate and sanitize message content.

    Args:
        message: Message content to validate

    Returns:
        Validated and sanitized message

    Raises:
        MessageValidationError: If validation fails
    """
    # Check if None
    if message is None:
        raise MessageValidationError("Message cannot be None")

    # Convert to string if needed
    message = str(message)

    # Check minimum length
    if len(message.strip()) < config.MIN_MESSAGE_LENGTH:
        raise MessageValidationError(
            f"Message too short. Minimum length is {config.MIN_MESSAGE_LENGTH} character"
        )

    # Check maximum length
    if len(message) > config.MAX_MESSAGE_LENGTH:
        raise MessageValidationError(
            f"Message too long. Maximum length is {config.MAX_MESSAGE_LENGTH} characters"
        )

    # Check for null bytes (security)
    if '\x00' in message:
        raise MessageValidationError("Message contains invalid characters")

    # Remove leading/trailing whitespace
    message = message.strip()

    return message

# ============================================================================
# Combined Validation
# ============================================================================

def validate_chat_request(session_id: str, message: str) -> tuple[str, str]:
    """
    Validate complete chat request including rate limiting.

    Args:
        session_id: Session identifier
        message: Message content

    Returns:
        Tuple of (validated_session_id, validated_message)

    Raises:
        ValidationError: If any validation fails
    """
    # Validate session ID
    validated_session_id = validate_session_id(session_id)

    # Validate message
    validated_message = validate_message(message)

    # Check rate limit
    rate_limiter.check_rate_limit(validated_session_id)

    return validated_session_id, validated_message

# ============================================================================
# Sanitization Helpers
# ============================================================================

def sanitize_html(text: str) -> str:
    """
    Basic HTML sanitization (additional to existing XSS protection).

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    # Replace dangerous HTML entities
    replacements = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text

def validate_and_sanitize_filename(filename: str) -> str:
    """
    Validate and sanitize filename (for future file upload features).

    Args:
        filename: Filename to validate

    Returns:
        Sanitized filename

    Raises:
        ValidationError: If validation fails
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")

    # Remove path traversal attempts
    filename = filename.replace('..', '').replace('/', '').replace('\\', '')

    # Allow only safe characters
    safe_filename = re.sub(r'[^\w\s.-]', '', filename)

    if not safe_filename:
        raise ValidationError("Invalid filename")

    return safe_filename
