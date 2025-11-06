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
# Table 5: Session Metadata (Session Management)
# ============================================================================

session_metadata = db.t.session_metadata
if session_metadata not in db.t:
    session_metadata.create(
        session_id=str,           # Primary key - unique session identifier
        name=str,                 # User-friendly session name
        created_at=str,           # ISO timestamp when session was created
        last_accessed=str,        # ISO timestamp of most recent activity
        message_count=int,        # Cached count of messages (for performance)
        icon=str,                 # Optional emoji icon for the session
        pk='session_id'
    )
    # Create index on last_accessed for sorting
    db.execute("CREATE INDEX IF NOT EXISTS idx_session_last_accessed ON session_metadata(last_accessed)")

# Generate SessionMetadata dataclass
SessionMetadata = session_metadata.dataclass()

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

    # Update message count in session metadata (if table exists)
    try:
        update_session_message_count(session_id)
    except Exception:
        # Silently ignore if session_metadata table doesn't exist
        # (for backwards compatibility with older databases/tests)
        pass

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
# Knowledge Graph Operations (PHASE 2 - ACTIVE)
# ============================================================================

def add_entity(
    session_id: str,
    entity_type: str,
    name: str,
    value: str,
    description: str = "",
    confidence: float = 1.0
) -> Entity:
    """
    Add or update an entity in the knowledge graph.

    If an entity with the same name already exists for this session,
    update its last_mentioned timestamp and increment mention_count.

    Args:
        session_id: The session identifier
        entity_type: Type of entity (person, date, fact, preference, relationship, location)
        name: Entity name (e.g., "John", "Mom's birthday")
        value: Entity value (e.g., "brother", "June 15")
        description: Optional context/notes
        confidence: Extraction confidence (0.0-1.0)

    Returns:
        The created or updated Entity object
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Check if entity already exists
    existing = db.execute(
        "SELECT * FROM entities WHERE session_id = ? AND name = ?",
        [session_id, name]
    ).fetchone()

    if existing:
        # Update existing entity
        entity_id = existing[0]
        db.execute(
            """UPDATE entities
               SET value = ?, description = ?, confidence = ?,
                   last_mentioned = ?, mention_count = mention_count + 1
               WHERE id = ?""",
            [value, description, confidence, timestamp, entity_id]
        )
        # Return updated entity
        return entities.get(entity_id)
    else:
        # Create new entity
        entity = entities.insert(
            session_id=session_id,
            entity_type=entity_type,
            name=name,
            value=value,
            description=description,
            confidence=confidence,
            created_at=timestamp,
            last_mentioned=timestamp,
            mention_count=1
        )
        return entity


def get_entities(
    session_id: str,
    entity_type: Optional[str] = None,
    min_confidence: float = 0.0
) -> list[dict]:
    """
    Retrieve entities from the knowledge graph.

    Args:
        session_id: The session identifier
        entity_type: Optional filter by entity type
        min_confidence: Minimum confidence threshold (default: 0.0)

    Returns:
        List of entity dictionaries
    """
    query = """
        SELECT id, entity_type, name, value, description, confidence,
               created_at, last_mentioned, mention_count
        FROM entities
        WHERE session_id = ? AND confidence >= ?
    """
    params = [session_id, min_confidence]

    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)

    query += " ORDER BY mention_count DESC, last_mentioned DESC"

    results = db.execute(query, params).fetchall()

    return [
        {
            "id": row[0],
            "entity_type": row[1],
            "name": row[2],
            "value": row[3],
            "description": row[4],
            "confidence": row[5],
            "created_at": row[6],
            "last_mentioned": row[7],
            "mention_count": row[8]
        }
        for row in results
    ]


def add_relationship(
    session_id: str,
    entity1_id: int,
    entity2_id: int,
    relationship_type: str,
    description: str = "",
    confidence: float = 1.0
) -> Relationship:
    """
    Add a relationship between two entities.

    Args:
        session_id: The session identifier
        entity1_id: ID of first entity
        entity2_id: ID of second entity
        relationship_type: Type of relationship (family, works_with, located_in, likes, birthday)
        description: Human-readable description (e.g., "is brother of", "birthday is")
        confidence: Extraction confidence (0.0-1.0)

    Returns:
        The created Relationship object
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    relationship = relationships.insert(
        session_id=session_id,
        entity1_id=entity1_id,
        entity2_id=entity2_id,
        relationship_type=relationship_type,
        description=description,
        confidence=confidence,
        created_at=timestamp
    )

    return relationship


def get_relationships(
    entity_id: int,
    min_confidence: float = 0.0
) -> list[dict]:
    """
    Get all relationships for a given entity.

    Args:
        entity_id: The entity ID to find relationships for
        min_confidence: Minimum confidence threshold

    Returns:
        List of relationship dictionaries with related entity info
    """
    query = """
        SELECT r.id, r.session_id, r.entity1_id, r.entity2_id,
               r.relationship_type, r.description, r.confidence, r.created_at,
               e1.name as entity1_name, e1.value as entity1_value,
               e2.name as entity2_name, e2.value as entity2_value
        FROM relationships r
        JOIN entities e1 ON r.entity1_id = e1.id
        JOIN entities e2 ON r.entity2_id = e2.id
        WHERE (r.entity1_id = ? OR r.entity2_id = ?)
          AND r.confidence >= ?
        ORDER BY r.created_at DESC
    """

    results = db.execute(query, [entity_id, entity_id, min_confidence]).fetchall()

    return [
        {
            "id": row[0],
            "session_id": row[1],
            "entity1_id": row[2],
            "entity2_id": row[3],
            "relationship_type": row[4],
            "description": row[5],
            "confidence": row[6],
            "created_at": row[7],
            "entity1_name": row[8],
            "entity1_value": row[9],
            "entity2_name": row[10],
            "entity2_value": row[11]
        }
        for row in results
    ]


def add_entity_mention(
    entity_id: int,
    message_id: int,
    mention_text: str
) -> EntityMention:
    """
    Record that an entity was mentioned in a message.

    Args:
        entity_id: ID of the entity
        message_id: ID of the message
        mention_text: Exact text from conversation

    Returns:
        The created EntityMention object
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    mention = entity_mentions.insert(
        entity_id=entity_id,
        message_id=message_id,
        mention_text=mention_text,
        extracted_at=timestamp
    )

    return mention


def build_context_from_entities(
    session_id: str,
    max_entities: int = 20,
    min_confidence: float = 0.5
) -> str:
    """
    Build a context string from the knowledge graph to inject into prompts.

    Args:
        session_id: The session identifier
        max_entities: Maximum number of entities to include
        min_confidence: Minimum confidence threshold

    Returns:
        Formatted context string for system prompt
    """
    entities_list = get_entities(session_id, min_confidence=min_confidence)

    if not entities_list:
        return ""

    # Limit to most relevant entities (by mention count and recency)
    entities_list = entities_list[:max_entities]

    # Build context string
    context_parts = ["# Knowledge Graph Context\n"]
    context_parts.append("The following facts about the user have been learned from previous conversations:\n")

    # Group by entity type
    by_type = {}
    for entity in entities_list:
        entity_type = entity["entity_type"]
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append(entity)

    # Format each type
    type_labels = {
        "person": "People",
        "date": "Important Dates",
        "fact": "Facts",
        "preference": "Preferences",
        "relationship": "Relationships",
        "location": "Locations"
    }

    for entity_type, type_entities in by_type.items():
        label = type_labels.get(entity_type, entity_type.capitalize())
        context_parts.append(f"\n## {label}")

        for entity in type_entities:
            name = entity["name"]
            value = entity["value"]
            description = entity["description"]

            if description:
                context_parts.append(f"- {name}: {value} ({description})")
            else:
                context_parts.append(f"- {name}: {value}")

    context_parts.append("\nUse this information naturally when relevant to the conversation.")

    return "\n".join(context_parts)


def delete_entity(entity_id: int) -> int:
    """
    Delete an entity and all associated relationships and mentions.

    Args:
        entity_id: The entity ID to delete

    Returns:
        Number of entities deleted (should be 1)
    """
    # Delete associated entity mentions
    db.execute("DELETE FROM entity_mentions WHERE entity_id = ?", [entity_id])

    # Delete associated relationships
    db.execute(
        "DELETE FROM relationships WHERE entity1_id = ? OR entity2_id = ?",
        [entity_id, entity_id]
    )

    # Delete the entity
    db.execute("DELETE FROM entities WHERE id = ?", [entity_id])

    return 1


def get_entity_by_name(session_id: str, name: str) -> Optional[dict]:
    """
    Get an entity by name for a specific session.

    Args:
        session_id: The session identifier
        name: The entity name to search for

    Returns:
        Entity dictionary or None if not found
    """
    result = db.execute(
        """SELECT id, entity_type, name, value, description, confidence,
                  created_at, last_mentioned, mention_count
           FROM entities
           WHERE session_id = ? AND name = ?""",
        [session_id, name]
    ).fetchone()

    if not result:
        return None

    return {
        "id": result[0],
        "entity_type": result[1],
        "name": result[2],
        "value": result[3],
        "description": result[4],
        "confidence": result[5],
        "created_at": result[6],
        "last_mentioned": result[7],
        "mention_count": result[8]
    }

# ============================================================================
# Session Management Operations
# ============================================================================

def create_session(session_id: str, name: str, icon: str = "💬") -> SessionMetadata:
    """
    Create a new session with metadata.

    Args:
        session_id: Unique session identifier
        name: User-friendly session name
        icon: Optional emoji icon (default: 💬)

    Returns:
        The created SessionMetadata object
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    session = session_metadata.insert(
        session_id=session_id,
        name=name,
        created_at=timestamp,
        last_accessed=timestamp,
        message_count=0,
        icon=icon
    )

    return session


def get_session(session_id: str) -> Optional[dict]:
    """
    Get session metadata by ID.

    Args:
        session_id: The session identifier

    Returns:
        Session metadata dictionary or None if not found
    """
    result = db.execute(
        """SELECT session_id, name, created_at, last_accessed, message_count, icon
           FROM session_metadata
           WHERE session_id = ?""",
        [session_id]
    ).fetchone()

    if not result:
        return None

    return {
        "session_id": result[0],
        "name": result[1],
        "created_at": result[2],
        "last_accessed": result[3],
        "message_count": result[4],
        "icon": result[5]
    }


def get_all_session_metadata() -> list[dict]:
    """
    Get all sessions ordered by most recent activity.

    Returns:
        List of session metadata dictionaries
    """
    results = db.execute(
        """SELECT session_id, name, created_at, last_accessed, message_count, icon
           FROM session_metadata
           ORDER BY last_accessed DESC"""
    ).fetchall()

    return [
        {
            "session_id": row[0],
            "name": row[1],
            "created_at": row[2],
            "last_accessed": row[3],
            "message_count": row[4],
            "icon": row[5]
        }
        for row in results
    ]


def update_session_name(session_id: str, new_name: str) -> bool:
    """
    Rename a session.

    Args:
        session_id: The session identifier
        new_name: New name for the session

    Returns:
        True if updated, False if session not found
    """
    # Check if session exists
    if not get_session(session_id):
        return False

    db.execute(
        "UPDATE session_metadata SET name = ? WHERE session_id = ?",
        [new_name, session_id]
    )

    return True


def update_session_icon(session_id: str, new_icon: str) -> bool:
    """
    Update session icon.

    Args:
        session_id: The session identifier
        new_icon: New emoji icon

    Returns:
        True if updated, False if session not found
    """
    if not get_session(session_id):
        return False

    db.execute(
        "UPDATE session_metadata SET icon = ? WHERE session_id = ?",
        [new_icon, session_id]
    )

    return True


def update_session_access(session_id: str) -> None:
    """
    Update last_accessed timestamp for a session.
    Creates session metadata if it doesn't exist.

    Args:
        session_id: The session identifier
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Check if session metadata exists
    existing = get_session(session_id)

    if existing:
        # Update last_accessed
        db.execute(
            "UPDATE session_metadata SET last_accessed = ? WHERE session_id = ?",
            [timestamp, session_id]
        )
    else:
        # Create new session metadata with default name
        create_session(session_id, f"Session {session_id[:8]}", "💬")


def update_session_message_count(session_id: str) -> None:
    """
    Update the cached message count for a session.

    Args:
        session_id: The session identifier
    """
    count = get_session_message_count(session_id)

    # Check if metadata exists
    if get_session(session_id):
        db.execute(
            "UPDATE session_metadata SET message_count = ? WHERE session_id = ?",
            [count, session_id]
        )
    else:
        # Create metadata if it doesn't exist
        update_session_access(session_id)
        db.execute(
            "UPDATE session_metadata SET message_count = ? WHERE session_id = ?",
            [count, session_id]
        )


def delete_session(session_id: str) -> int:
    """
    Delete a session and ALL associated data.
    This includes messages, entities, relationships, and entity mentions.

    Args:
        session_id: The session identifier

    Returns:
        Total number of records deleted
    """
    deleted_count = 0

    # Delete messages
    deleted_count += db.execute(
        "DELETE FROM messages WHERE session_id = ?",
        [session_id]
    ).rowcount if hasattr(db.execute("DELETE FROM messages WHERE session_id = ?", [session_id]), 'rowcount') else 0

    # Get all entities for this session
    entities_to_delete = db.execute(
        "SELECT id FROM entities WHERE session_id = ?",
        [session_id]
    ).fetchall()

    entity_ids = [row[0] for row in entities_to_delete]

    # Delete entity mentions
    for entity_id in entity_ids:
        db.execute("DELETE FROM entity_mentions WHERE entity_id = ?", [entity_id])
        deleted_count += 1

    # Delete relationships
    for entity_id in entity_ids:
        db.execute(
            "DELETE FROM relationships WHERE entity1_id = ? OR entity2_id = ?",
            [entity_id, entity_id]
        )
        deleted_count += 1

    # Delete entities
    db.execute("DELETE FROM entities WHERE session_id = ?", [session_id])
    deleted_count += len(entity_ids)

    # Delete session metadata
    db.execute("DELETE FROM session_metadata WHERE session_id = ?", [session_id])
    deleted_count += 1

    return deleted_count


def ensure_session_metadata_exists(session_id: str, default_name: str = None) -> None:
    """
    Ensure session metadata exists, creating it if necessary.
    Useful for migrating existing sessions that don't have metadata.

    Args:
        session_id: The session identifier
        default_name: Default name to use if creating new metadata
    """
    if not get_session(session_id):
        name = default_name or f"Session {session_id[:8]}"
        create_session(session_id, name, "💬")

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
