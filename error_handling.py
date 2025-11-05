"""
PromptPane Error Handling

This module contains error handling functionality including:
- User-friendly error message generation
- Retry logic with exponential backoff
- Debug command handling for testing
"""

import time
import logging
from typing import Callable, Optional, Any
from collections.abc import Callable as CallableType

# Import configuration
import config

# Import debug commands from constants
from constants import DEBUG_COMMANDS

# ============================================================================
# Logging Configuration
# ============================================================================

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# ============================================================================
# Error Message Formatting
# ============================================================================

def get_user_friendly_error_message(error: Exception) -> tuple[str, bool]:
    """
    Convert technical errors into user-friendly messages.

    Args:
        error: The exception object

    Returns:
        Tuple of (user_message, should_retry)
    """
    error_str: str = str(error).lower()

    # Rate limiting errors
    if 'rate limit' in error_str or '429' in error_str:
        return (
            "⏳ **Rate Limit Reached**\n\n"
            "The AI service is currently experiencing high demand. "
            "Please wait a moment and try again.\n\n"
            "*Your message has been saved and you can retry by sending it again.*",
            True
        )

    # Authentication errors
    if 'api key' in error_str or 'authentication' in error_str or '401' in error_str or '403' in error_str:
        return (
            "🔑 **Authentication Error**\n\n"
            "There's an issue with the API key configuration. "
            "Please check that your GROQ_API_KEY is set correctly in the `.env` file.\n\n"
            "*Contact the administrator if this problem persists.*",
            False
        )

    # Network/connection errors
    if 'connection' in error_str or 'network' in error_str or 'timeout' in error_str:
        return (
            "🌐 **Connection Issue**\n\n"
            "Unable to reach the AI service. This could be due to:\n"
            "- Network connectivity problems\n"
            "- Service temporarily unavailable\n"
            "- Request timeout\n\n"
            "*Please check your internet connection and try again.*",
            True
        )

    # Service unavailable
    if '503' in error_str or 'service unavailable' in error_str:
        return (
            "🔧 **Service Temporarily Unavailable**\n\n"
            "The AI service is currently down for maintenance or experiencing issues. "
            "Please try again in a few minutes.\n\n"
            "*This is usually temporary and should resolve soon.*",
            True
        )

    # Content policy violations
    if 'content policy' in error_str or 'content filter' in error_str:
        return (
            "⚠️ **Content Policy Violation**\n\n"
            "Your message was flagged by the content policy filter. "
            "Please rephrase your question and try again.\n\n"
            "*Ensure your message follows community guidelines.*",
            False
        )

    # Invalid request
    if 'invalid' in error_str or '400' in error_str:
        return (
            "❌ **Invalid Request**\n\n"
            "There was a problem processing your request. "
            "This might be due to:\n"
            "- Message too long\n"
            "- Invalid characters\n"
            "- Malformed request\n\n"
            "*Try rephrasing your message or making it shorter.*",
            False
        )

    # Model errors
    if 'model' in error_str:
        return (
            "🤖 **Model Error**\n\n"
            "There's an issue with the AI model configuration. "
            "The requested model may be unavailable or deprecated.\n\n"
            "*Contact the administrator to check the model settings.*",
            False
        )

    # Generic error
    logger.error(f"Unexpected error: {error}", exc_info=True)
    return (
        "❌ **Unexpected Error**\n\n"
        "Something went wrong while processing your request. "
        f"Error details: `{str(error)[:100]}`\n\n"
        "*Please try again. If the problem persists, contact support.*",
        True
    )

# ============================================================================
# Retry Logic
# ============================================================================

def retry_with_exponential_backoff(
    func: Callable[[], Any],
    max_retries: Optional[int] = None,
    initial_delay: Optional[int] = None,
    max_delay: Optional[int] = None
) -> Any:
    """
    Retry a function with exponential backoff for transient failures.

    Args:
        func: Function to retry (should be a callable that takes no arguments)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Result from the function if successful

    Raises:
        The last exception if all retries fail
    """
    # Use config defaults if not specified
    if max_retries is None:
        max_retries = config.RETRY_MAX_ATTEMPTS
    if initial_delay is None:
        initial_delay = config.RETRY_INITIAL_DELAY
    if max_delay is None:
        max_delay = config.RETRY_MAX_DELAY

    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()

            # Don't retry non-transient errors
            if any(x in error_str for x in ['api key', 'authentication', '401', '403', 'invalid', '400', 'content policy']):
                logger.warning(f"Non-retryable error on attempt {attempt + 1}: {e}")
                raise

            # Calculate delay with exponential backoff
            delay = min(initial_delay * (2 ** attempt), max_delay)

            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {e}")

    raise last_exception

# ============================================================================
# Debug Commands - For testing error handling from chat interface
# ============================================================================

def is_debug_command(message: str) -> bool:
    """Check if message is a debug command"""
    return message.strip() in DEBUG_COMMANDS

def handle_debug_command(message: str) -> Optional[str]:
    """
    Execute debug command by raising appropriate error.

    Args:
        message: The debug command string

    Returns:
        Help message string if command is /debug-help, None otherwise

    Raises:
        Appropriate exception based on command
    """
    command: str = message.strip()

    logger.info(f"Executing debug command: {command}")

    if command == '/test-rate-limit':
        raise Exception("Rate limit exceeded. Error code: 429. Please try again later.")

    elif command == '/test-auth-error':
        raise Exception("Authentication failed. Invalid API key. Error code: 401.")

    elif command == '/test-network-error':
        raise Exception("Connection timeout: Unable to reach the server. Network error occurred.")

    elif command == '/test-service-down':
        raise Exception("Service unavailable. Error code: 503. The service is temporarily down.")

    elif command == '/test-invalid-request':
        raise Exception("Invalid request format. Error code: 400. Bad request.")

    elif command == '/test-model-error':
        raise Exception("Model 'test-invalid-model' not found. Please check model configuration.")

    elif command == '/test-content-policy':
        raise Exception("Content policy violation detected. Your message was flagged by content filter.")

    elif command == '/test-unknown-error':
        raise Exception("An unexpected error occurred in the quantum flux capacitor module.")

    elif command == '/debug-help':
        help_msg = "🔧 **Debug Commands Available:**\n\n"
        for cmd, desc in DEBUG_COMMANDS.items():
            help_msg += f"- `{cmd}` - {desc}\n"
        help_msg += "\n*These commands help test error handling without breaking anything.*"
        return help_msg

    return None
