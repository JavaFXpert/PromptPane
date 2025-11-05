"""
Unit tests for entity extraction and knowledge graph functionality

Tests the entity extraction module and database knowledge graph operations.
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
from entity_extraction import should_extract_entities

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
    db.entities = entities
    db.relationships = relationships
    db.entity_mentions = entity_mentions

    yield test_db

    # Cleanup
    db.db = original_db
    db.messages = original_db.t.messages
    db.entities = original_db.t.entities
    db.relationships = original_db.t.relationships
    db.entity_mentions = original_db.t.entity_mentions
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
# Entity CRUD Tests
# ============================================================================

@pytest.mark.unit
class TestAddEntity:
    """Tests for adding entities to knowledge graph"""

    def test_add_entity_creates_entity(self, temp_db, sample_session_id):
        """Test that add_entity creates a new entity"""
        entity = db.add_entity(
            session_id=sample_session_id,
            entity_type="person",
            name="John",
            value="brother",
            description="lives in Seattle",
            confidence=0.95
        )

        # Verify entity was created
        entities = db.get_entities(sample_session_id)
        assert len(entities) == 1
        assert entities[0]["name"] == "John"
        assert entities[0]["value"] == "brother"
        assert entities[0]["entity_type"] == "person"
        assert entities[0]["confidence"] == 0.95

    def test_add_entity_updates_existing(self, temp_db, sample_session_id):
        """Test that adding duplicate entity updates it"""
        # Add entity first time
        db.add_entity(
            session_id=sample_session_id,
            entity_type="person",
            name="John",
            value="brother",
            confidence=0.9
        )

        # Add same entity again with different value
        db.add_entity(
            session_id=sample_session_id,
            entity_type="person",
            name="John",
            value="older brother",
            confidence=0.95
        )

        # Should only have one entity
        entities = db.get_entities(sample_session_id)
        assert len(entities) == 1
        assert entities[0]["value"] == "older brother"
        assert entities[0]["mention_count"] == 2

    def test_add_different_entity_types(self, temp_db, sample_session_id):
        """Test adding different types of entities"""
        db.add_entity(sample_session_id, "person", "Mom", "mother", confidence=1.0)
        db.add_entity(sample_session_id, "date", "Mom's birthday", "06-15", confidence=0.95)
        db.add_entity(sample_session_id, "preference", "beverage", "tea", confidence=0.8)
        db.add_entity(sample_session_id, "location", "home", "Seattle", confidence=0.9)

        entities = db.get_entities(sample_session_id)
        assert len(entities) == 4

        # Check all types are present
        types = {e["entity_type"] for e in entities}
        assert types == {"person", "date", "preference", "location"}

@pytest.mark.unit
class TestGetEntities:
    """Tests for retrieving entities from knowledge graph"""

    def test_get_entities_returns_empty_for_new_session(self, temp_db):
        """Test that get_entities returns empty list for new session"""
        entities = db.get_entities("new-session")
        assert entities == []

    def test_get_entities_filters_by_type(self, temp_db, sample_session_id):
        """Test filtering entities by type"""
        db.add_entity(sample_session_id, "person", "John", "brother")
        db.add_entity(sample_session_id, "person", "Mom", "mother")
        db.add_entity(sample_session_id, "date", "birthday", "06-15")

        people = db.get_entities(sample_session_id, entity_type="person")
        assert len(people) == 2
        assert all(e["entity_type"] == "person" for e in people)

        dates = db.get_entities(sample_session_id, entity_type="date")
        assert len(dates) == 1
        assert dates[0]["entity_type"] == "date"

    def test_get_entities_filters_by_confidence(self, temp_db, sample_session_id):
        """Test filtering entities by confidence threshold"""
        db.add_entity(sample_session_id, "fact", "high_conf", "value", confidence=0.95)
        db.add_entity(sample_session_id, "fact", "med_conf", "value", confidence=0.7)
        db.add_entity(sample_session_id, "fact", "low_conf", "value", confidence=0.4)

        # Get entities with min confidence 0.8
        high_conf_entities = db.get_entities(sample_session_id, min_confidence=0.8)
        assert len(high_conf_entities) == 1
        assert high_conf_entities[0]["name"] == "high_conf"

        # Get entities with min confidence 0.5
        medium_conf_entities = db.get_entities(sample_session_id, min_confidence=0.5)
        assert len(medium_conf_entities) == 2

    def test_get_entities_orders_by_relevance(self, temp_db, sample_session_id):
        """Test that entities are ordered by mention count and recency"""
        # Add entities in different order
        db.add_entity(sample_session_id, "person", "John", "brother")
        db.add_entity(sample_session_id, "person", "Mom", "mother")

        # Mention John multiple times
        db.add_entity(sample_session_id, "person", "John", "brother")
        db.add_entity(sample_session_id, "person", "John", "brother")

        entities = db.get_entities(sample_session_id)

        # John should be first (higher mention count)
        assert entities[0]["name"] == "John"
        assert entities[0]["mention_count"] == 3
        assert entities[1]["name"] == "Mom"
        assert entities[1]["mention_count"] == 1

@pytest.mark.unit
class TestRelationships:
    """Tests for relationship management"""

    def test_add_relationship(self, temp_db, sample_session_id):
        """Test adding relationships between entities"""
        # Create two entities
        john = db.add_entity(sample_session_id, "person", "John", "person")
        mom = db.add_entity(sample_session_id, "person", "Mom", "mother")

        # Get their IDs
        entities = db.get_entities(sample_session_id)
        john_id = next(e["id"] for e in entities if e["name"] == "John")
        mom_id = next(e["id"] for e in entities if e["name"] == "Mom")

        # Add relationship
        db.add_relationship(
            session_id=sample_session_id,
            entity1_id=john_id,
            entity2_id=mom_id,
            relationship_type="family",
            description="is son of",
            confidence=0.95
        )

        # Get relationships
        john_rels = db.get_relationships(john_id)
        assert len(john_rels) == 1
        assert john_rels[0]["relationship_type"] == "family"
        assert john_rels[0]["description"] == "is son of"

    def test_get_relationships_bidirectional(self, temp_db, sample_session_id):
        """Test that relationships are bidirectional"""
        # Create entities and relationship
        john = db.add_entity(sample_session_id, "person", "John", "person")
        mom = db.add_entity(sample_session_id, "person", "Mom", "mother")

        entities = db.get_entities(sample_session_id)
        john_id = next(e["id"] for e in entities if e["name"] == "John")
        mom_id = next(e["id"] for e in entities if e["name"] == "Mom")

        db.add_relationship(
            session_id=sample_session_id,
            entity1_id=john_id,
            entity2_id=mom_id,
            relationship_type="family",
            description="is son of"
        )

        # Should find relationship from both entities
        john_rels = db.get_relationships(john_id)
        mom_rels = db.get_relationships(mom_id)

        assert len(john_rels) == 1
        assert len(mom_rels) == 1
        assert john_rels[0]["id"] == mom_rels[0]["id"]

@pytest.mark.unit
class TestBuildContext:
    """Tests for building context from knowledge graph"""

    def test_build_context_empty_when_no_entities(self, temp_db, sample_session_id):
        """Test that context is empty when no entities exist"""
        context = db.build_context_from_entities(sample_session_id)
        assert context == ""

    def test_build_context_includes_entities(self, temp_db, sample_session_id):
        """Test that context includes entities"""
        db.add_entity(sample_session_id, "person", "John", "brother", "software engineer", 0.95)
        db.add_entity(sample_session_id, "date", "Mom's birthday", "06-15", "", 0.9)

        context = db.build_context_from_entities(sample_session_id)

        assert "Knowledge Graph Context" in context
        assert "John" in context
        assert "brother" in context
        assert "Mom's birthday" in context
        assert "06-15" in context

    def test_build_context_respects_confidence_threshold(self, temp_db, sample_session_id):
        """Test that low confidence entities are filtered out"""
        db.add_entity(sample_session_id, "person", "High", "value", confidence=0.9)
        db.add_entity(sample_session_id, "person", "Low", "value", confidence=0.3)

        context = db.build_context_from_entities(sample_session_id, min_confidence=0.5)

        assert "High" in context
        assert "Low" not in context

    def test_build_context_respects_max_entities(self, temp_db, sample_session_id):
        """Test that max_entities limit is respected"""
        # Add 10 entities
        for i in range(10):
            db.add_entity(sample_session_id, "fact", f"fact_{i}", f"value_{i}", confidence=0.9)

        context = db.build_context_from_entities(sample_session_id, max_entities=5)

        # Should only include 5 entities
        entity_count = context.count("fact_")
        assert entity_count == 5

    def test_build_context_groups_by_type(self, temp_db, sample_session_id):
        """Test that context groups entities by type"""
        db.add_entity(sample_session_id, "person", "John", "brother")
        db.add_entity(sample_session_id, "date", "birthday", "06-15")
        db.add_entity(sample_session_id, "preference", "food", "pizza")

        context = db.build_context_from_entities(sample_session_id)

        assert "## People" in context
        assert "## Important Dates" in context
        assert "## Preferences" in context

@pytest.mark.unit
class TestDeleteEntity:
    """Tests for deleting entities"""

    def test_delete_entity_removes_entity(self, temp_db, sample_session_id):
        """Test that delete_entity removes the entity"""
        db.add_entity(sample_session_id, "person", "John", "brother")

        entities = db.get_entities(sample_session_id)
        entity_id = entities[0]["id"]

        db.delete_entity(entity_id)

        entities_after = db.get_entities(sample_session_id)
        assert len(entities_after) == 0

    def test_delete_entity_removes_relationships(self, temp_db, sample_session_id):
        """Test that deleting entity also deletes its relationships"""
        # Create entities and relationship
        db.add_entity(sample_session_id, "person", "John", "person")
        db.add_entity(sample_session_id, "person", "Mom", "mother")

        entities = db.get_entities(sample_session_id)
        john_id = next(e["id"] for e in entities if e["name"] == "John")
        mom_id = next(e["id"] for e in entities if e["name"] == "Mom")

        db.add_relationship(
            session_id=sample_session_id,
            entity1_id=john_id,
            entity2_id=mom_id,
            relationship_type="family",
            description="is son of"
        )

        # Delete John
        db.delete_entity(john_id)

        # Relationship should be gone
        mom_rels = db.get_relationships(mom_id)
        assert len(mom_rels) == 0

@pytest.mark.unit
class TestGetEntityByName:
    """Tests for getting entity by name"""

    def test_get_entity_by_name_returns_entity(self, temp_db, sample_session_id):
        """Test that get_entity_by_name finds entity"""
        db.add_entity(sample_session_id, "person", "John", "brother")

        entity = db.get_entity_by_name(sample_session_id, "John")

        assert entity is not None
        assert entity["name"] == "John"
        assert entity["value"] == "brother"

    def test_get_entity_by_name_returns_none_when_not_found(self, temp_db, sample_session_id):
        """Test that get_entity_by_name returns None for missing entity"""
        entity = db.get_entity_by_name(sample_session_id, "NonExistent")
        assert entity is None

    def test_get_entity_by_name_session_isolation(self, temp_db):
        """Test that entities are isolated by session"""
        db.add_entity("session-1", "person", "John", "brother")

        # Should not find in different session
        entity = db.get_entity_by_name("session-2", "John")
        assert entity is None

# ============================================================================
# Entity Extraction Tests
# ============================================================================

@pytest.mark.unit
class TestShouldExtractEntities:
    """Tests for should_extract_entities heuristic"""

    def test_should_extract_from_personal_info(self):
        """Test that extraction happens for personal information"""
        user_msg = "My brother John lives in Seattle"
        assistant_msg = "That's nice! Seattle is a beautiful city."

        assert should_extract_entities(user_msg, assistant_msg) is True

    def test_should_not_extract_from_pure_questions(self):
        """Test that pure questions without personal info are skipped"""
        user_msg = "What is the weather like?"
        assistant_msg = "I don't have access to real-time weather data."

        assert should_extract_entities(user_msg, assistant_msg) is False

    def test_should_not_extract_from_very_short_messages(self):
        """Test that very short messages are skipped"""
        user_msg = "Hi"
        assistant_msg = "Hello!"

        assert should_extract_entities(user_msg, assistant_msg) is False

    def test_should_extract_from_preferences(self):
        """Test that preferences are extracted"""
        user_msg = "I prefer tea over coffee"
        assistant_msg = "That's a good choice!"

        assert should_extract_entities(user_msg, assistant_msg) is True

    def test_should_not_extract_from_errors(self):
        """Test that error responses are skipped"""
        user_msg = "Tell me about my family"
        assistant_msg = "I'm sorry, I don't have that information."

        assert should_extract_entities(user_msg, assistant_msg) is False
