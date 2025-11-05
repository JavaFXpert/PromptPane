"""
Database module for PromptPane

Handles SQLite database operations for conversation storage and future
knowledge graph functionality using FastHTML's fastlite library.

Schema Design:
- messages: Raw conversation storage (ACTIVE)
- entities: Knowledge graph entities (READY FOR PHASE 2)
- relationships: Entity relationships (READY FOR PHASE 2)
- entity_mentions: Entity mention tracking (READY FOR PHASE 2)
"""

import os
from datetime import datetime, timezone
from typing import Optional
from fasthtml.common import database
import config

# ============================================================================
# Database Initialization
# ============================================================================

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

# Initialize database connection
db = database(config.DATABASE_PATH)

# Enable Write-Ahead Logging for better concurrency
db.execute("PRAGMA journal_mode=WAL")
db.execute(f"PRAGMA busy_timeout={config.DATABASE_TIMEOUT * 1000}")

# ============================================================================
# Table 1: Messages (ACTIVE - Used immediately)
# ============================================================================

messages = db.t.messages
if messages not in db.t:
    messages.create(
        id=int,
        session_id=str,
        role=str,
        content=str,
        timestamp=str,
        pk='id'
    )
    # Create indexes for fast lookups
    db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")

# Generate Message dataclass
Message = messages.dataclass()

# ============================================================================
# Table 2: Entities (READY FOR PHASE 2 - Knowledge Graph)
# ============================================================================

entities = db.t.entities
if entities not in db.t:
    entities.create(
        id=int,
        session_id=str,
        entity_type=str,      # person, date, fact, preference, relationship, location
        name=str,             # Entity name (e.g., "John", "Mom's birthday")
        value=str,            # Entity value (e.g., "brother", "June 15")
        description=str,      # Optional context/notes
        confidence=float,     # Extraction confidence (0.0-1.0)
        created_at=str,       # ISO timestamp when first discovered
        last_mentioned=str,   # ISO timestamp of most recent mention
        mention_count=int,    # How many times mentioned
        pk='id'
    )
    # Create indexes
    db.execute("CREATE INDEX IF NOT EXISTS idx_entities_session ON entities(session_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")

# Generate Entity dataclass
Entity = entities.dataclass()

# ============================================================================
# Table 3: Relationships (READY FOR PHASE 2 - Knowledge Graph)
# ============================================================================

relationships = db.t.relationships
if relationships not in db.t:
    relationships.create(
        id=int,
        session_id=str,
        entity1_id=int,           # Foreign key to entities
        entity2_id=int,           # Foreign key to entities
        relationship_type=str,    # family, works_with, located_in, likes, birthday
        description=str,          # Human-readable description
        confidence=float,         # Extraction confidence (0.0-1.0)
        created_at=str,          # ISO timestamp
        pk='id'
    )
    # Create indexes
    db.execute("CREATE INDEX IF NOT EXISTS idx_relationships_session ON relationships(session_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_relationships_entity1 ON relationships(entity1_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_relationships_entity2 ON relationships(entity2_id)")

# Generate Relationship dataclass
Relationship = relationships.dataclass()

# ============================================================================
# Table 4: Entity Mentions (READY FOR PHASE 2 - Audit Trail)
# ============================================================================

entity_mentions = db.t.entity_mentions
if entity_mentions not in db.t:
    entity_mentions.create(
        id=int,
        entity_id=int,        # Foreign key to entities
        message_id=int,       # Foreign key to messages
        mention_text=str,     # Exact text from conversation
        extracted_at=str,     # ISO timestamp
        pk='id'
    )
    # Create indexes
    db.execute("CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_mentions_message ON entity_mentions(message_id)")

# Generate EntityMention dataclass
EntityMention = entity_mentions.dataclass()

# ============================================================================
# Message CRUD Operations (ACTIVE)
# ============================================================================

def get_conversation(session_id: str, limit: Optional[int] = None) -> list[dict]:
    """
    Retrieve all messages for a conversation session.

    Args:
        session_id: The session identifier
        limit: Optional limit on number of messages (None = all messages)

    Returns:
        List of message dictionaries with role, content, and timestamp
    """
    if limit is None:
        limit = config.DATABASE_MAX_MESSAGES_PER_SESSION

    # Query messages ordered by timestamp
    query = "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC"

    if limit:
        query += f" LIMIT {limit}"

    results = db.execute(query, [session_id]).fetchall()

    # Convert to list of dicts for compatibility with existing code
    return [
        {
            "role": row[0],
            "content": row[1],
            "timestamp": row[2]
        }
        for row in results
    ]


def add_message(session_id: str, role: str, content: str) -> Message:
    """
    Add a new message to the conversation.

    Args:
        session_id: The session identifier
        role: Message role ('user' or 'assistant')
        content: Message content (markdown/HTML)

    Returns:
        The created Message object
    """
    # Generate UTC timestamp
    timestamp = datetime.now(timezone.utc).isoformat()

    # Insert message
    msg = messages.insert(
        session_id=session_id,
        role=role,
        content=content,
        timestamp=timestamp
    )

    return msg


def clear_conversation(session_id: str) -> int:
    """
    Delete all messages for a session.

    Args:
        session_id: The session identifier

    Returns:
        Number of messages deleted
    """
    # Count messages before deletion
    count_query = "SELECT COUNT(*) FROM messages WHERE session_id = ?"
    count = db.execute(count_query, [session_id]).fetchone()[0]

    # Delete all messages for this session
    db.execute("DELETE FROM messages WHERE session_id = ?", [session_id])

    return count


def get_all_sessions() -> list[str]:
    """
    Get list of all unique session IDs ordered by most recent activity.

    Returns:
        List of session IDs
    """
    query = """
        SELECT session_id
        FROM messages
        GROUP BY session_id
        ORDER BY MAX(timestamp) DESC
    """
    results = db.execute(query).fetchall()
    return [row[0] for row in results]


def get_session_message_count(session_id: str) -> int:
    """
    Get the number of messages in a session.

    Args:
        session_id: The session identifier

    Returns:
        Message count
    """
    query = "SELECT COUNT(*) FROM messages WHERE session_id = ?"
    return db.execute(query, [session_id]).fetchone()[0]


def delete_old_messages(days: int = 30) -> int:
    """
    Delete messages older than specified number of days.
    Optional maintenance function for cleanup.

    Args:
        days: Number of days to retain (default: 30)

    Returns:
        Number of messages deleted
    """
    from datetime import timedelta

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Count messages to delete
    count_query = "SELECT COUNT(*) FROM messages WHERE timestamp < ?"
    count = db.execute(count_query, [cutoff_date]).fetchone()[0]

    # Delete old messages
    db.execute("DELETE FROM messages WHERE timestamp < ?", [cutoff_date])

    return count


# ============================================================================
# Knowledge Graph Operations (READY FOR PHASE 2)
# ============================================================================

# TODO: Implement in Phase 2
# - extract_entities_from_message(message_id: int) -> list[Entity]
# - add_entity(session_id: str, entity_type: str, name: str, value: str) -> Entity
# - get_entities(session_id: str, entity_type: Optional[str] = None) -> list[Entity]
# - add_relationship(entity1_id: int, entity2_id: int, rel_type: str) -> Relationship
# - get_relationships(entity_id: int) -> list[Relationship]
# - build_context_from_entities(session_id: str) -> str

# ============================================================================
# Database Utilities
# ============================================================================

def initialize_database() -> None:
    """
    Initialize database and ensure all tables exist.
    Called on application startup.
    """
    # Tables are created automatically when this module is imported
    # This function exists for explicit initialization if needed
    pass


def get_database_stats() -> dict:
    """
    Get database statistics for monitoring/debugging.

    Returns:
        Dictionary with database stats
    """
    stats = {
        "database_path": config.DATABASE_PATH,
        "message_count": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        "session_count": len(get_all_sessions()),
        "entity_count": db.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
        "relationship_count": db.execute("SELECT COUNT(*) FROM relationships").fetchone()[0],
        "database_size_mb": os.path.getsize(config.DATABASE_PATH) / (1024 * 1024) if os.path.exists(config.DATABASE_PATH) else 0
    }
    return stats


def check_database_integrity() -> bool:
    """
    Check database integrity.

    Returns:
        True if database is healthy, False otherwise
    """
    try:
        result = db.execute("PRAGMA integrity_check").fetchone()
        return result[0] == "ok"
    except Exception:
        return False
