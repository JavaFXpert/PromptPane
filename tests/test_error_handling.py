"""
Unit tests for error_handling.py

Tests for error message formatting, retry logic, and debug commands.
"""

import pytest
import time
from unittest.mock import Mock, patch
from error_handling import (
    get_user_friendly_error_message,
    retry_with_exponential_backoff,
    is_debug_command,
    handle_debug_command
)

# ============================================================================
# Error Message Formatting Tests
# ============================================================================

@pytest.mark.unit
class TestGetUserFriendlyErrorMessage:
    """Tests for get_user_friendly_error_message()"""

    def test_rate_limit_error_detected(self):
        """Test rate limit error (429) is detected and formatted"""
        error = Exception("Rate limit exceeded. Error code: 429")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Rate Limit" in message
        assert should_retry is True

    def test_auth_error_detected(self):
        """Test authentication error (401) is detected and formatted"""
        error = Exception("Authentication failed. Error code: 401")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Authentication" in message
        assert should_retry is False

    def test_api_key_error_detected(self):
        """Test API key error is detected and formatted"""
        error = Exception("Invalid API key provided")

        message, should_retry = get_user_friendly_error_message(error)

        assert "API key" in message or "Authentication" in message
        assert should_retry is False

    def test_network_error_detected(self):
        """Test network/connection error is detected"""
        error = Exception("Connection timeout")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Connection" in message or "Network" in message
        assert should_retry is True

    def test_service_unavailable_error_detected(self):
        """Test service unavailable (503) is detected"""
        error = Exception("Service unavailable. Error code: 503")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Unavailable" in message or "Service" in message
        assert should_retry is True

    def test_content_policy_error_detected(self):
        """Test content policy violation is detected"""
        error = Exception("Content policy violation detected")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Content" in message or "policy" in message
        assert should_retry is False

    def test_invalid_request_error_detected(self):
        """Test invalid request (400) is detected"""
        error = Exception("Invalid request. Error code: 400")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Invalid" in message
        assert should_retry is False

    def test_model_error_detected(self):
        """Test model error is detected"""
        error = Exception("Model 'test-model' not found")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Model" in message
        assert should_retry is False

    def test_generic_error_has_fallback(self):
        """Test unknown error returns generic message"""
        error = Exception("Some unknown error occurred")

        message, should_retry = get_user_friendly_error_message(error)

        assert "Unexpected" in message or "Error" in message
        assert should_retry is True

    def test_error_message_includes_emoji(self):
        """Test error messages include emoji indicators"""
        errors = [
            ("Rate limit", "429"),
            ("API key", "401"),
            ("Connection", "network"),
        ]

        for error_text, keyword in errors:
            error = Exception(f"{error_text} with {keyword}")
            message, _ = get_user_friendly_error_message(error)
            # Should have some emoji character
            assert any(c in message for c in ['⏳', '🔑', '🌐', '❌', '⚠️', '🔧', '🤖'])

# ============================================================================
# Retry Logic Tests
# ============================================================================

@pytest.mark.unit
class TestRetryWithExponentialBackoff:
    """Tests for retry_with_exponential_backoff()"""

    def test_successful_call_on_first_attempt(self):
        """Test successful function call returns immediately"""
        mock_func = Mock(return_value="success")

        result = retry_with_exponential_backoff(mock_func, max_retries=3)

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retries_on_transient_error(self):
        """Test function is retried on transient error"""
        mock_func = Mock(side_effect=[
            Exception("Network timeout"),
            Exception("Network timeout"),
            "success"
        ])

        result = retry_with_exponential_backoff(mock_func, max_retries=3, initial_delay=0.01, max_delay=0.1)

        assert result == "success"
        assert mock_func.call_count == 3

    def test_does_not_retry_on_auth_error(self):
        """Test function is not retried on authentication error"""
        mock_func = Mock(side_effect=Exception("API key invalid. Error: 401"))

        with pytest.raises(Exception, match="API key"):
            retry_with_exponential_backoff(mock_func, max_retries=3)

        assert mock_func.call_count == 1  # Should not retry

    def test_does_not_retry_on_invalid_request(self):
        """Test function is not retried on invalid request (400)"""
        mock_func = Mock(side_effect=Exception("Invalid request. Error: 400"))

        with pytest.raises(Exception, match="Invalid"):
            retry_with_exponential_backoff(mock_func, max_retries=3)

        assert mock_func.call_count == 1  # Should not retry

    def test_raises_last_exception_after_max_retries(self):
        """Test raises last exception after exhausting retries"""
        error = Exception("Persistent error")
        mock_func = Mock(side_effect=error)

        with pytest.raises(Exception, match="Persistent error"):
            retry_with_exponential_backoff(mock_func, max_retries=3, initial_delay=0.01)

        assert mock_func.call_count == 3

    def test_exponential_backoff_delays(self):
        """Test delays increase exponentially"""
        mock_func = Mock(side_effect=[
            Exception("Timeout"),
            Exception("Timeout"),
            "success"
        ])

        start_time = time.time()
        retry_with_exponential_backoff(mock_func, max_retries=3, initial_delay=0.1, max_delay=1)
        elapsed = time.time() - start_time

        # With initial_delay=0.1: first retry ~0.1s, second retry ~0.2s
        # Total should be at least 0.3s
        assert elapsed >= 0.25  # Allow some margin

    def test_respects_max_delay(self):
        """Test delay does not exceed max_delay"""
        mock_func = Mock(side_effect=[
            Exception("Timeout"),
            Exception("Timeout"),
            Exception("Timeout"),
            "success"
        ])

        start_time = time.time()
        # With initial_delay=1 and max_delay=0.5, all delays should be capped at 0.5
        retry_with_exponential_backoff(mock_func, max_retries=4, initial_delay=1, max_delay=0.5)
        elapsed = time.time() - start_time

        # Should not take longer than 3 * max_delay (with some margin)
        assert elapsed < 2.5  # 3 retries * 0.5s + margin

    def test_uses_config_defaults_when_none(self):
        """Test uses config values when parameters are None"""
        mock_func = Mock(return_value="success")

        with patch('error_handling.config.RETRY_MAX_ATTEMPTS', 5):
            result = retry_with_exponential_backoff(mock_func, max_retries=None)

        assert result == "success"
        assert mock_func.call_count == 1

# ============================================================================
# Debug Command Tests
# ============================================================================

@pytest.mark.unit
class TestDebugCommands:
    """Tests for debug command functions"""

    def test_is_debug_command_recognizes_valid_command(self):
        """Test is_debug_command recognizes valid commands"""
        assert is_debug_command("/test-rate-limit") is True
        assert is_debug_command("/test-auth-error") is True
        assert is_debug_command("/debug-help") is True

    def test_is_debug_command_with_whitespace(self):
        """Test is_debug_command handles whitespace"""
        assert is_debug_command("  /test-rate-limit  ") is True

    def test_is_debug_command_rejects_invalid_command(self):
        """Test is_debug_command rejects invalid commands"""
        assert is_debug_command("/invalid-command") is False
        assert is_debug_command("not a command") is False
        assert is_debug_command("") is False

    def test_handle_debug_command_rate_limit(self):
        """Test /test-rate-limit raises appropriate error"""
        with pytest.raises(Exception, match="Rate limit"):
            handle_debug_command("/test-rate-limit")

    def test_handle_debug_command_auth_error(self):
        """Test /test-auth-error raises appropriate error"""
        with pytest.raises(Exception, match="Authentication|API key"):
            handle_debug_command("/test-auth-error")

    def test_handle_debug_command_network_error(self):
        """Test /test-network-error raises appropriate error"""
        with pytest.raises(Exception, match="Connection|Network"):
            handle_debug_command("/test-network-error")

    def test_handle_debug_command_service_down(self):
        """Test /test-service-down raises appropriate error"""
        with pytest.raises(Exception, match="Service|503"):
            handle_debug_command("/test-service-down")

    def test_handle_debug_command_invalid_request(self):
        """Test /test-invalid-request raises appropriate error"""
        with pytest.raises(Exception, match="Invalid|400"):
            handle_debug_command("/test-invalid-request")

    def test_handle_debug_command_model_error(self):
        """Test /test-model-error raises appropriate error"""
        with pytest.raises(Exception, match="Model"):
            handle_debug_command("/test-model-error")

    def test_handle_debug_command_content_policy(self):
        """Test /test-content-policy raises appropriate error"""
        with pytest.raises(Exception, match="Content policy"):
            handle_debug_command("/test-content-policy")

    def test_handle_debug_command_unknown_error(self):
        """Test /test-unknown-error raises appropriate error"""
        with pytest.raises(Exception):
            handle_debug_command("/test-unknown-error")

    def test_handle_debug_help_returns_help_text(self):
        """Test /debug-help returns help message"""
        result = handle_debug_command("/debug-help")

        assert result is not None
        assert "Debug Commands" in result
        assert "/test-rate-limit" in result
        assert "/test-auth-error" in result

# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.unit
class TestErrorHandlingIntegration:
    """Integration tests for error handling flow"""

    def test_retry_with_friendly_message(self):
        """Test retry logic with error message formatting"""
        # Simulate function that fails then succeeds
        call_count = [0]

        def flaky_function():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Network timeout occurred")
            return "success"

        # Should retry and succeed
        result = retry_with_exponential_backoff(flaky_function, max_retries=5, initial_delay=0.01)
        assert result == "success"
        assert call_count[0] == 3

    def test_non_retryable_error_with_friendly_message(self):
        """Test non-retryable error provides friendly message"""
        def failing_function():
            raise Exception("Invalid API key. Error: 401")

        # Should fail immediately
        with pytest.raises(Exception):
            retry_with_exponential_backoff(failing_function, max_retries=3)

        # Should get friendly error message
        try:
            failing_function()
        except Exception as e:
            message, should_retry = get_user_friendly_error_message(e)
            assert should_retry is False
            assert "Authentication" in message or "API key" in message
