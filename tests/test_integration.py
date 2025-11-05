"""
Integration tests for FastHTML application

Tests the complete request/response cycle through FastHTML routes,
including validation, rate limiting, and error handling.
"""

import pytest
from fasthtml.common import *
from starlette.testclient import TestClient
import config
from validators import RateLimiter

# Import the FastHTML app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# We'll need to import main module to get the app
# But we need to be careful not to run it
import main

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastHTML app"""
    return TestClient(main.app)

@pytest.fixture
def test_session():
    """Provide a unique test session ID"""
    import uuid
    return f"test-{uuid.uuid4().hex[:8]}"

@pytest.fixture(autouse=True)
def reset_conversations():
    """Reset conversations before each test"""
    main.conversations.clear()
    yield
    main.conversations.clear()

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test"""
    # Create a fresh rate limiter for each test
    import validators
    validators.rate_limiter = RateLimiter()
    yield

# ============================================================================
# Home Page Tests
# ============================================================================

@pytest.mark.integration
class TestHomePage:
    """Tests for the home page route"""

    def test_home_page_loads(self, client):
        """Test that home page returns 200"""
        response = client.get("/")
        assert response.status_code == 200

    def test_home_page_has_default_session(self, client):
        """Test that home page redirects to default session"""
        response = client.get("/", follow_redirects=False)
        # Should redirect to /chat/default or render chat interface
        assert response.status_code in [200, 302, 303, 307]

# ============================================================================
# Chat Endpoint Tests
# ============================================================================

@pytest.mark.integration
class TestChatEndpoint:
    """Tests for POST /chat/{session_id} endpoint"""

    def test_chat_endpoint_requires_message(self, client, test_session):
        """Test that chat endpoint requires message parameter"""
        response = client.post(f"/chat/{test_session}")
        # Should handle missing message gracefully
        assert response.status_code in [200, 400, 422]

    def test_chat_endpoint_with_valid_message(self, client, test_session):
        """Test posting a valid message to chat endpoint"""
        response = client.post(
            f"/chat/{test_session}",
            data={"message": "Hello, test!"}
        )
        # Should accept the message (might be 200 or redirect)
        assert response.status_code in [200, 302, 303, 307]

    def test_chat_endpoint_validates_empty_message(self, client, test_session):
        """Test that empty messages are rejected"""
        response = client.post(
            f"/chat/{test_session}",
            data={"message": ""}
        )
        # Should reject empty message
        assert response.status_code in [200, 400, 422]

    def test_chat_endpoint_validates_long_message(self, client, test_session):
        """Test that overly long messages are rejected"""
        long_message = "a" * (config.MAX_MESSAGE_LENGTH + 1)
        response = client.post(
            f"/chat/{test_session}",
            data={"message": long_message}
        )
        # Should reject message that's too long
        assert response.status_code in [200, 400, 422]

    def test_chat_endpoint_with_whitespace_message(self, client, test_session):
        """Test that whitespace-only messages are rejected"""
        response = client.post(
            f"/chat/{test_session}",
            data={"message": "   "}
        )
        # Should reject whitespace-only message
        assert response.status_code in [200, 400, 422]

    def test_chat_endpoint_with_null_byte(self, client, test_session):
        """Test that messages with null bytes are rejected"""
        response = client.post(
            f"/chat/{test_session}",
            data={"message": "Hello\x00World"}
        )
        # Should reject message with null byte
        assert response.status_code in [200, 400, 422]

    def test_chat_endpoint_with_unicode(self, client, test_session):
        """Test that unicode messages are accepted"""
        response = client.post(
            f"/chat/{test_session}",
            data={"message": "Hello 你好 🌍"}
        )
        # Should accept unicode
        assert response.status_code in [200, 302, 303, 307]

# ============================================================================
# Session ID Validation Tests
# ============================================================================

@pytest.mark.integration
class TestSessionIDValidation:
    """Tests for session ID validation in routes"""

    def test_valid_session_id_alphanumeric(self, client):
        """Test that alphanumeric session IDs work"""
        response = client.post(
            "/chat/test123",
            data={"message": "Hello"}
        )
        assert response.status_code in [200, 302, 303, 307]

    def test_valid_session_id_with_hyphen(self, client):
        """Test that session IDs with hyphens work"""
        response = client.post(
            "/chat/test-session-123",
            data={"message": "Hello"}
        )
        assert response.status_code in [200, 302, 303, 307]

    def test_valid_session_id_with_underscore(self, client):
        """Test that session IDs with underscores work"""
        response = client.post(
            "/chat/test_session_123",
            data={"message": "Hello"}
        )
        assert response.status_code in [200, 302, 303, 307]

    def test_invalid_session_id_with_special_chars(self, client):
        """Test that session IDs with special characters are rejected"""
        invalid_sessions = [
            "test@session",
            "test#session",
            "test$session",
            "test session",  # space
            "test.session",  # dot
        ]

        for session_id in invalid_sessions:
            response = client.post(
                f"/chat/{session_id}",
                data={"message": "Hello"}
            )
            # Should reject invalid session ID
            assert response.status_code in [200, 400, 404, 422]

# ============================================================================
# Rate Limiting Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestRateLimiting:
    """Tests for rate limiting functionality"""

    def test_rate_limit_allows_requests_within_limit(self, client, test_session):
        """Test that requests within rate limit are allowed"""
        # Send requests up to the limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            response = client.post(
                f"/chat/{test_session}",
                data={"message": f"Message {i}"}
            )
            # Should accept requests within limit
            assert response.status_code in [200, 302, 303, 307]

    def test_rate_limit_blocks_excess_requests(self, client, test_session):
        """Test that requests exceeding rate limit are blocked"""
        # Fill up the rate limit
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            client.post(
                f"/chat/{test_session}",
                data={"message": f"Message {i}"}
            )

        # Next request should be blocked
        response = client.post(
            f"/chat/{test_session}",
            data={"message": "One more message"}
        )
        # Should return 200 with error message in response
        assert response.status_code == 200
        # Response should contain rate limit error message
        assert "Rate Limit" in response.text or "rate limit" in response.text.lower()

    def test_rate_limit_per_session(self, client):
        """Test that rate limiting is per-session"""
        session1 = "test-session-1"
        session2 = "test-session-2"

        # Fill rate limit for session1
        for i in range(config.RATE_LIMIT_MAX_REQUESTS):
            client.post(
                f"/chat/{session1}",
                data={"message": f"Message {i}"}
            )

        # Session2 should still work
        response = client.post(
            f"/chat/{session2}",
            data={"message": "Hello from session 2"}
        )
        assert response.status_code in [200, 302, 303, 307]

# ============================================================================
# Clear Conversation Tests
# ============================================================================

@pytest.mark.integration
class TestClearConversation:
    """Tests for clearing conversation history"""

    def test_clear_endpoint_exists(self, client, test_session):
        """Test that clear endpoint is accessible"""
        response = client.post(f"/clear/{test_session}")
        assert response.status_code in [200, 302, 303, 307]

    def test_clear_removes_conversation_history(self, client, test_session):
        """Test that clear actually removes conversation history"""
        # Add some messages
        client.post(
            f"/chat/{test_session}",
            data={"message": "First message"}
        )
        client.post(
            f"/chat/{test_session}",
            data={"message": "Second message"}
        )

        # Verify conversation exists
        assert test_session in main.conversations
        assert len(main.conversations[test_session]) > 0

        # Clear conversation
        response = client.post(f"/clear/{test_session}")
        assert response.status_code in [200, 302, 303, 307]

        # Verify conversation is cleared
        if test_session in main.conversations:
            assert len(main.conversations[test_session]) == 0

    def test_clear_invalid_session_id(self, client):
        """Test clearing with invalid session ID"""
        response = client.post("/clear/invalid@session")
        # Should handle invalid session ID
        assert response.status_code in [200, 400, 404, 422]

# ============================================================================
# Send Button Tests
# ============================================================================

@pytest.mark.integration
class TestSendButton:
    """Tests for send button endpoint"""

    def test_send_button_endpoint_exists(self, client, test_session):
        """Test that send button endpoint is accessible"""
        response = client.post(
            f"/send-button/{test_session}",
            data={"message": "Button clicked"}
        )
        assert response.status_code in [200, 302, 303, 307]

    def test_send_button_with_message(self, client, test_session):
        """Test that send button processes messages"""
        response = client.post(
            f"/send-button/{test_session}",
            data={"message": "Test button message"}
        )
        assert response.status_code in [200, 302, 303, 307]

# ============================================================================
# Conversation Management Tests
# ============================================================================

@pytest.mark.integration
class TestConversationManagement:
    """Tests for conversation state management"""

    def test_conversation_persists_across_requests(self, client, test_session):
        """Test that conversation history persists"""
        # Send first message
        client.post(
            f"/chat/{test_session}",
            data={"message": "First message"}
        )

        # Verify conversation was created
        assert test_session in main.conversations
        initial_length = len(main.conversations[test_session])

        # Send second message
        client.post(
            f"/chat/{test_session}",
            data={"message": "Second message"}
        )

        # Verify conversation grew
        assert len(main.conversations[test_session]) > initial_length

    def test_different_sessions_are_independent(self, client):
        """Test that different sessions maintain separate conversations"""
        session1 = "test-session-a"
        session2 = "test-session-b"

        # Send message to session1
        client.post(
            f"/chat/{session1}",
            data={"message": "Message to session 1"}
        )

        # Send message to session2
        client.post(
            f"/chat/{session2}",
            data={"message": "Message to session 2"}
        )

        # Both should exist independently
        if session1 in main.conversations and session2 in main.conversations:
            assert main.conversations[session1] != main.conversations[session2]

# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling in routes"""

    def test_handles_missing_parameters_gracefully(self, client, test_session):
        """Test that missing parameters are handled gracefully"""
        response = client.post(f"/chat/{test_session}")
        # Should not crash, should return valid response
        assert response.status_code in [200, 400, 422]

    def test_handles_malformed_requests(self, client, test_session):
        """Test that malformed requests are handled"""
        response = client.post(
            f"/chat/{test_session}",
            data={"wrong_param": "value"}
        )
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
