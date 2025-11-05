"""
Unit tests for database module

Tests the SQLite database operations including message storage,
conversation management, and database utilities.
"""

import pytest
import os
import tempfile
from datetime import datetime, timezone, timedelta
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import after path modification
import config
import db

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Override config to use temp database
    original_path = config.DATABASE_PATH
    config.DATABASE_PATH = path

    # Re-initialize database with temp path
    from fasthtml.common import database
    test_db = database(path)

    # Create messages table
    messages = test_db.t.messages
    if messages not in test_db.t:
        messages.create(
            id=int,
            session_id=str,
            role=str,
            content=str,
            timestamp=str,
            pk='id'
        )
        test_db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        test_db.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")

    # Create entities table (for knowledge graph Phase 2)
    entities = test_db.t.entities
    if entities not in test_db.t:
        entities.create(
            id=int,
            session_id=str,
            entity_type=str,
            name=str,
            value=str,
            description=str,
            confidence=float,
            created_at=str,
            last_mentioned=str,
            mention_count=int,
            pk='id'
        )

    # Create relationships table (for knowledge graph Phase 2)
    relationships = test_db.t.relationships
    if relationships not in test_db.t:
        relationships.create(
            id=int,
            session_id=str,
            entity1_id=int,
            entity2_id=int,
            relationship_type=str,
            description=str,
            confidence=float,
            created_at=str,
            pk='id'
        )

    # Override db module's database connection
    original_db = db.db
    db.db = test_db
    db.messages = messages

    yield test_db

    # Cleanup
    db.db = original_db
    db.messages = original_db.t.messages
    config.DATABASE_PATH = original_path

    # Remove temp file
    try:
        os.unlink(path)
    except:
        pass

@pytest.fixture
def sample_session_id():
    """Provide a sample session ID for testing"""
    return "test-session-123"

# ============================================================================
# Message CRUD Tests
# ============================================================================

@pytest.mark.unit
class TestAddMessage:
    """Tests for adding messages to the database"""

    def test_add_message_creates_message(self, temp_db, sample_session_id):
        """Test that add_message creates a message in the database"""
        msg = db.add_message(sample_session_id, "user", "Hello, world!")

        # Verify message was added by retrieving conversation
        conversation = db.get_conversation(sample_session_id)
        assert len(conversation) == 1
        assert conversation[0]["role"] == "user"
        assert conversation[0]["content"] == "Hello, world!"
        assert conversation[0]["timestamp"] is not None

    def test_add_message_generates_timestamp(self, temp_db, sample_session_id):
        """Test that add_message generates a valid ISO timestamp"""
        db.add_message(sample_session_id, "user", "Test message")

        # Retrieve and verify timestamp
        conversation = db.get_conversation(sample_session_id)
        timestamp_str = conversation[0]["timestamp"]

        # Verify timestamp is valid ISO format
        timestamp = datetime.fromisoformat(timestamp_str)
        assert timestamp is not None

        # Verify timestamp is recent (within last minute)
        now = datetime.now(timezone.utc)
        delta = now - timestamp
        assert delta.total_seconds() < 60

    def test_add_message_handles_unicode(self, temp_db, sample_session_id):
        """Test that add_message handles unicode content"""
        db.add_message(sample_session_id, "user", "Hello 你好 🌍")

        conversation = db.get_conversation(sample_session_id)
        assert conversation[0]["content"] == "Hello 你好 🌍"

    def test_add_message_handles_markdown(self, temp_db, sample_session_id):
        """Test that add_message handles markdown content"""
        markdown_content = "# Heading\n\n**Bold** and *italic*"
        db.add_message(sample_session_id, "user", markdown_content)

        conversation = db.get_conversation(sample_session_id)
        assert conversation[0]["content"] == markdown_content

    def test_add_multiple_messages(self, temp_db, sample_session_id):
        """Test adding multiple messages to same session"""
        db.add_message(sample_session_id, "user", "First message")
        db.add_message(sample_session_id, "assistant", "Second message")
        db.add_message(sample_session_id, "user", "Third message")

        conversation = db.get_conversation(sample_session_id)
        assert len(conversation) == 3
        assert conversation[0]["content"] == "First message"
        assert conversation[1]["content"] == "Second message"
        assert conversation[2]["content"] == "Third message"

@pytest.mark.unit
class TestGetConversation:
    """Tests for retrieving conversation history"""

    def test_get_conversation_returns_empty_for_new_session(self, temp_db):
        """Test that get_conversation returns empty list for new session"""
        conversation = db.get_conversation("new-session")

        assert conversation == []

    def test_get_conversation_returns_messages(self, temp_db, sample_session_id):
        """Test that get_conversation returns all messages for a session"""
        db.add_message(sample_session_id, "user", "First")
        db.add_message(sample_session_id, "assistant", "Second")
        db.add_message(sample_session_id, "user", "Third")

        conversation = db.get_conversation(sample_session_id)

        assert len(conversation) == 3
        assert conversation[0]["role"] == "user"
        assert conversation[0]["content"] == "First"
        assert conversation[1]["role"] == "assistant"
        assert conversation[1]["content"] == "Second"
        assert conversation[2]["role"] == "user"
        assert conversation[2]["content"] == "Third"

    def test_get_conversation_orders_by_timestamp(self, temp_db, sample_session_id):
        """Test that messages are returned in chronological order"""
        db.add_message(sample_session_id, "user", "Message 1")
        db.add_message(sample_session_id, "assistant", "Message 2")
        db.add_message(sample_session_id, "user", "Message 3")

        conversation = db.get_conversation(sample_session_id)

        # Verify timestamps are in ascending order
        timestamps = [datetime.fromisoformat(msg["timestamp"]) for msg in conversation]
        assert timestamps == sorted(timestamps)

    def test_get_conversation_respects_limit(self, temp_db, sample_session_id):
        """Test that get_conversation respects the limit parameter"""
        for i in range(10):
            db.add_message(sample_session_id, "user", f"Message {i}")

        conversation = db.get_conversation(sample_session_id, limit=5)

        assert len(conversation) == 5

    def test_get_conversation_separates_sessions(self, temp_db):
        """Test that conversations are isolated by session ID"""
        db.add_message("session-1", "user", "Session 1 message")
        db.add_message("session-2", "user", "Session 2 message")

        conv1 = db.get_conversation("session-1")
        conv2 = db.get_conversation("session-2")

        assert len(conv1) == 1
        assert len(conv2) == 1
        assert conv1[0]["content"] == "Session 1 message"
        assert conv2[0]["content"] == "Session 2 message"

    def test_get_conversation_returns_dict_format(self, temp_db, sample_session_id):
        """Test that get_conversation returns messages as dicts with correct keys"""
        db.add_message(sample_session_id, "user", "Test")

        conversation = db.get_conversation(sample_session_id)

        assert len(conversation) == 1
        assert "role" in conversation[0]
        assert "content" in conversation[0]
        assert "timestamp" in conversation[0]

@pytest.mark.unit
class TestClearConversation:
    """Tests for clearing conversation history"""

    def test_clear_conversation_deletes_messages(self, temp_db, sample_session_id):
        """Test that clear_conversation deletes all messages for a session"""
        db.add_message(sample_session_id, "user", "Message 1")
        db.add_message(sample_session_id, "assistant", "Message 2")
        db.add_message(sample_session_id, "user", "Message 3")

        count = db.clear_conversation(sample_session_id)

        assert count == 3
        assert db.get_conversation(sample_session_id) == []

    def test_clear_conversation_returns_count(self, temp_db, sample_session_id):
        """Test that clear_conversation returns number of deleted messages"""
        for i in range(5):
            db.add_message(sample_session_id, "user", f"Message {i}")

        count = db.clear_conversation(sample_session_id)

        assert count == 5

    def test_clear_conversation_handles_empty_session(self, temp_db):
        """Test that clearing an empty session returns 0"""
        count = db.clear_conversation("nonexistent-session")

        assert count == 0

    def test_clear_conversation_preserves_other_sessions(self, temp_db):
        """Test that clearing one session doesn't affect others"""
        db.add_message("session-1", "user", "Session 1")
        db.add_message("session-2", "user", "Session 2")

        db.clear_conversation("session-1")

        assert db.get_conversation("session-1") == []
        assert len(db.get_conversation("session-2")) == 1

# ============================================================================
# Session Management Tests
# ============================================================================

@pytest.mark.unit
class TestGetAllSessions:
    """Tests for retrieving all session IDs"""

    def test_get_all_sessions_returns_empty_initially(self, temp_db):
        """Test that get_all_sessions returns empty list when no sessions exist"""
        sessions = db.get_all_sessions()

        assert sessions == []

    def test_get_all_sessions_returns_session_ids(self, temp_db):
        """Test that get_all_sessions returns all unique session IDs"""
        db.add_message("session-1", "user", "Message 1")
        db.add_message("session-2", "user", "Message 2")
        db.add_message("session-1", "assistant", "Message 3")

        sessions = db.get_all_sessions()

        assert len(sessions) == 2
        assert "session-1" in sessions
        assert "session-2" in sessions

    def test_get_all_sessions_orders_by_recent_activity(self, temp_db):
        """Test that sessions are ordered by most recent activity"""
        db.add_message("old-session", "user", "Old message")
        db.add_message("new-session", "user", "New message")

        sessions = db.get_all_sessions()

        # Most recent should be first
        assert sessions[0] == "new-session"
        assert sessions[1] == "old-session"

@pytest.mark.unit
class TestGetSessionMessageCount:
    """Tests for getting message count per session"""

    def test_get_session_message_count_returns_zero_for_new_session(self, temp_db):
        """Test that message count is 0 for new session"""
        count = db.get_session_message_count("new-session")

        assert count == 0

    def test_get_session_message_count_returns_correct_count(self, temp_db, sample_session_id):
        """Test that message count is accurate"""
        for i in range(7):
            db.add_message(sample_session_id, "user", f"Message {i}")

        count = db.get_session_message_count(sample_session_id)

        assert count == 7

    def test_get_session_message_count_updates_after_clear(self, temp_db, sample_session_id):
        """Test that message count updates after clearing"""
        for i in range(5):
            db.add_message(sample_session_id, "user", f"Message {i}")

        db.clear_conversation(sample_session_id)
        count = db.get_session_message_count(sample_session_id)

        assert count == 0

# ============================================================================
# Database Utilities Tests
# ============================================================================

@pytest.mark.unit
class TestDatabaseStats:
    """Tests for database statistics"""

    def test_get_database_stats_returns_dict(self, temp_db):
        """Test that get_database_stats returns a dictionary"""
        stats = db.get_database_stats()

        assert isinstance(stats, dict)

    def test_get_database_stats_includes_required_keys(self, temp_db):
        """Test that stats include all required keys"""
        stats = db.get_database_stats()

        assert "database_path" in stats
        assert "message_count" in stats
        assert "session_count" in stats
        assert "entity_count" in stats
        assert "relationship_count" in stats
        assert "database_size_mb" in stats

    def test_get_database_stats_reflects_message_count(self, temp_db, sample_session_id):
        """Test that message count in stats is accurate"""
        for i in range(3):
            db.add_message(sample_session_id, "user", f"Message {i}")

        stats = db.get_database_stats()

        assert stats["message_count"] == 3

@pytest.mark.unit
class TestDatabaseIntegrity:
    """Tests for database integrity checking"""

    def test_check_database_integrity_returns_true(self, temp_db):
        """Test that integrity check returns True for healthy database"""
        result = db.check_database_integrity()

        assert result is True

# ============================================================================
# Data Validation Tests
# ============================================================================

@pytest.mark.unit
class TestDataValidation:
    """Tests for data validation and edge cases"""

    def test_add_message_with_empty_content(self, temp_db, sample_session_id):
        """Test adding message with empty content"""
        db.add_message(sample_session_id, "user", "")

        conversation = db.get_conversation(sample_session_id)
        assert conversation[0]["content"] == ""

    def test_add_message_with_very_long_content(self, temp_db, sample_session_id):
        """Test adding message with very long content"""
        long_content = "a" * 100000
        db.add_message(sample_session_id, "user", long_content)

        conversation = db.get_conversation(sample_session_id)
        assert conversation[0]["content"] == long_content

    def test_add_message_with_special_characters(self, temp_db, sample_session_id):
        """Test adding message with special characters"""
        special_content = "Special: <>&\"'\\n\\t"
        db.add_message(sample_session_id, "user", special_content)

        conversation = db.get_conversation(sample_session_id)
        assert conversation[0]["content"] == special_content

    def test_session_id_with_special_characters(self, temp_db):
        """Test session IDs with hyphens and underscores"""
        session_ids = ["test-session", "test_session", "test-123_abc"]

        for session_id in session_ids:
            db.add_message(session_id, "user", "Test")
            conversation = db.get_conversation(session_id)
            assert len(conversation) >= 1

# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.slow
class TestPerformance:
    """Tests for database performance with larger datasets"""

    def test_add_many_messages(self, temp_db, sample_session_id):
        """Test adding many messages performs reasonably"""
        for i in range(100):
            db.add_message(sample_session_id, "user", f"Message {i}")

        count = db.get_session_message_count(sample_session_id)
        assert count == 100

    def test_get_conversation_with_many_messages(self, temp_db, sample_session_id):
        """Test retrieving conversation with many messages"""
        for i in range(50):
            db.add_message(sample_session_id, "user", f"Message {i}")

        conversation = db.get_conversation(sample_session_id)

        assert len(conversation) == 50
        assert conversation[0]["content"] == "Message 0"
        assert conversation[49]["content"] == "Message 49"
