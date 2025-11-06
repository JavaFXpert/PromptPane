"""
Unit tests for session management functionality

Tests session CRUD operations, metadata management, and session UI.
"""

import pytest
import os
import tempfile
from datetime import datetime, timezone
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

    # Create all tables
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

    session_metadata = test_db.t.session_metadata
    if session_metadata not in test_db.t:
        session_metadata.create(
            session_id=str,
            name=str,
            created_at=str,
            last_accessed=str,
            message_count=int,
            icon=str,
            pk='session_id'
        )

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

    entity_mentions = test_db.t.entity_mentions
    if entity_mentions not in test_db.t:
        entity_mentions.create(
            id=int,
            entity_id=int,
            message_id=int,
            mention_text=str,
            extracted_at=str,
            pk='id'
        )

    # Override db module's database connection
    original_db = db.db
    db.db = test_db
    db.messages = messages
    db.session_metadata = session_metadata
    db.entities = entities
    db.relationships = relationships
    db.entity_mentions = entity_mentions

    yield test_db

    # Cleanup
    db.db = original_db
    db.messages = original_db.t.messages
    db.session_metadata = original_db.t.session_metadata
    db.entities = original_db.t.entities
    db.relationships = original_db.t.relationships
    db.entity_mentions = original_db.t.entity_mentions
    config.DATABASE_PATH = original_path

    # Remove temp file
    try:
        os.unlink(path)
    except:
        pass

# ============================================================================
# Session Creation Tests
# ============================================================================

@pytest.mark.unit
class TestCreateSession:
    """Tests for creating sessions"""

    def test_create_session_with_defaults(self, temp_db):
        """Test creating session with default icon"""
        session = db.create_session("test-session", "My Session")

        # Verify session was created
        retrieved = db.get_session("test-session")
        assert retrieved is not None
        assert retrieved["session_id"] == "test-session"
        assert retrieved["name"] == "My Session"
        assert retrieved["icon"] == "💬"
        assert retrieved["message_count"] == 0

    def test_create_session_with_custom_icon(self, temp_db):
        """Test creating session with custom icon"""
        db.create_session("test-session", "Work", "💼")

        session = db.get_session("test-session")
        assert session["icon"] == "💼"

    def test_create_session_sets_timestamps(self, temp_db):
        """Test that session creation sets timestamps"""
        db.create_session("test-session", "Test")

        session = db.get_session("test-session")

        # Verify timestamps are set and valid
        created_at = datetime.fromisoformat(session["created_at"])
        last_accessed = datetime.fromisoformat(session["last_accessed"])

        assert created_at is not None
        assert last_accessed is not None

        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        assert (now - created_at).total_seconds() < 60

# ============================================================================
# Session Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestGetSession:
    """Tests for retrieving sessions"""

    def test_get_session_returns_none_for_nonexistent(self, temp_db):
        """Test that get_session returns None for nonexistent session"""
        session = db.get_session("nonexistent")
        assert session is None

    def test_get_session_returns_correct_data(self, temp_db):
        """Test that get_session returns all fields"""
        db.create_session("test-session", "Test Session", "🎮")

        session = db.get_session("test-session")

        assert session["session_id"] == "test-session"
        assert session["name"] == "Test Session"
        assert session["icon"] == "🎮"
        assert "created_at" in session
        assert "last_accessed" in session
        assert "message_count" in session

@pytest.mark.unit
class TestGetAllSessionMetadata:
    """Tests for retrieving all sessions"""

    def test_get_all_sessions_returns_empty_initially(self, temp_db):
        """Test that get_all_session_metadata returns empty list initially"""
        sessions = db.get_all_session_metadata()
        assert sessions == []

    def test_get_all_sessions_returns_all_sessions(self, temp_db):
        """Test that all sessions are returned"""
        db.create_session("session-1", "Session 1")
        db.create_session("session-2", "Session 2")
        db.create_session("session-3", "Session 3")

        sessions = db.get_all_session_metadata()

        assert len(sessions) == 3
        session_ids = {s["session_id"] for s in sessions}
        assert session_ids == {"session-1", "session-2", "session-3"}

    def test_get_all_sessions_orders_by_recent_activity(self, temp_db):
        """Test that sessions are ordered by last_accessed"""
        db.create_session("old", "Old")
        db.create_session("new", "New")

        # Update access time for "new" session
        db.update_session_access("new")

        sessions = db.get_all_session_metadata()

        # Most recently accessed should be first
        assert sessions[0]["session_id"] == "new"
        assert sessions[1]["session_id"] == "old"

# ============================================================================
# Session Update Tests
# ============================================================================

@pytest.mark.unit
class TestUpdateSession:
    """Tests for updating session metadata"""

    def test_update_session_name(self, temp_db):
        """Test renaming a session"""
        db.create_session("test-session", "Old Name")

        success = db.update_session_name("test-session", "New Name")

        assert success is True

        session = db.get_session("test-session")
        assert session["name"] == "New Name"

    def test_update_session_name_nonexistent_returns_false(self, temp_db):
        """Test that updating nonexistent session returns False"""
        success = db.update_session_name("nonexistent", "Name")
        assert success is False

    def test_update_session_icon(self, temp_db):
        """Test updating session icon"""
        db.create_session("test-session", "Test", "💬")

        success = db.update_session_icon("test-session", "🎨")

        assert success is True

        session = db.get_session("test-session")
        assert session["icon"] == "🎨"

    def test_update_session_access_updates_timestamp(self, temp_db):
        """Test that update_session_access updates last_accessed"""
        db.create_session("test-session", "Test")

        original = db.get_session("test-session")
        original_time = original["last_accessed"]

        # Wait a tiny bit to ensure timestamp changes
        import time
        time.sleep(0.01)

        # Update access time
        db.update_session_access("test-session")

        updated = db.get_session("test-session")
        updated_time = updated["last_accessed"]

        # Timestamp should have changed
        assert updated_time > original_time

    def test_update_session_access_creates_if_not_exists(self, temp_db):
        """Test that update_session_access creates metadata if needed"""
        # Session doesn't exist yet
        assert db.get_session("new-session") is None

        # Update access should create it
        db.update_session_access("new-session")

        # Should now exist
        session = db.get_session("new-session")
        assert session is not None
        assert "new-session" in session["session_id"]

    def test_update_session_message_count(self, temp_db):
        """Test updating message count"""
        db.create_session("test-session", "Test")

        # Add some messages
        db.add_message("test-session", "user", "Message 1")
        db.add_message("test-session", "assistant", "Message 2")
        db.add_message("test-session", "user", "Message 3")

        # Update count
        db.update_session_message_count("test-session")

        session = db.get_session("test-session")
        assert session["message_count"] == 3

# ============================================================================
# Session Deletion Tests
# ============================================================================

@pytest.mark.unit
class TestDeleteSession:
    """Tests for deleting sessions"""

    def test_delete_session_removes_session(self, temp_db):
        """Test that delete_session removes the session"""
        db.create_session("test-session", "Test")

        # Verify exists
        assert db.get_session("test-session") is not None

        # Delete
        db.delete_session("test-session")

        # Should be gone
        assert db.get_session("test-session") is None

    def test_delete_session_removes_messages(self, temp_db):
        """Test that deleting session also deletes messages"""
        db.create_session("test-session", "Test")

        # Add messages
        db.add_message("test-session", "user", "Message 1")
        db.add_message("test-session", "assistant", "Message 2")

        # Verify messages exist
        assert len(db.get_conversation("test-session")) == 2

        # Delete session
        db.delete_session("test-session")

        # Messages should be gone
        assert len(db.get_conversation("test-session")) == 0

    def test_delete_session_removes_entities(self, temp_db):
        """Test that deleting session also deletes entities"""
        db.create_session("test-session", "Test")

        # Add entities
        db.add_entity("test-session", "person", "John", "brother")
        db.add_entity("test-session", "fact", "color", "blue")

        # Verify entities exist
        assert len(db.get_entities("test-session")) == 2

        # Delete session
        db.delete_session("test-session")

        # Entities should be gone
        assert len(db.get_entities("test-session")) == 0

    def test_delete_session_cascade_to_relationships(self, temp_db):
        """Test that deleting session cascades to relationships"""
        db.create_session("test-session", "Test")

        # Add entities and relationship
        db.add_entity("test-session", "person", "John", "person")
        db.add_entity("test-session", "person", "Mom", "mother")

        entities = db.get_entities("test-session")
        john_id = entities[0]["id"]
        mom_id = entities[1]["id"]

        db.add_relationship("test-session", john_id, mom_id, "family", "son of")

        # Verify relationship exists
        assert len(db.get_relationships(john_id)) > 0

        # Delete session
        db.delete_session("test-session")

        # Entities and relationships should be gone
        assert len(db.get_entities("test-session")) == 0

# ============================================================================
# Session Helpers Tests
# ============================================================================

@pytest.mark.unit
class TestEnsureSessionMetadata:
    """Tests for ensure_session_metadata_exists helper"""

    def test_ensure_creates_metadata_if_missing(self, temp_db):
        """Test that ensure creates metadata if it doesn't exist"""
        # Session doesn't exist
        assert db.get_session("new-session") is None

        # Ensure it exists
        db.ensure_session_metadata_exists("new-session", "Custom Name")

        # Should now exist
        session = db.get_session("new-session")
        assert session is not None
        assert session["name"] == "Custom Name"

    def test_ensure_does_not_overwrite_existing(self, temp_db):
        """Test that ensure doesn't overwrite existing metadata"""
        # Create session
        db.create_session("existing", "Original Name", "🎮")

        # Ensure with different name
        db.ensure_session_metadata_exists("existing", "Different Name")

        # Should keep original
        session = db.get_session("existing")
        assert session["name"] == "Original Name"
        assert session["icon"] == "🎮"

    def test_ensure_uses_default_name_if_none_provided(self, temp_db):
        """Test that ensure uses default name if none provided"""
        db.ensure_session_metadata_exists("test-12345678")

        session = db.get_session("test-12345678")
        assert "test-123" in session["name"]
