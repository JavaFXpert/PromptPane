"""
Knowledge Graph Manager

LLM-based knowledge graph curation system that uses semantic understanding
to intelligently update entities and relationships.

Instead of algorithmic deduplication, we pass the entire knowledge graph
to the LLM and let it decide how to update it based on new conversations.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional, Any
import config

# Path to knowledge graph JSON file
KG_FILE_PATH = os.path.join(os.path.dirname(__file__), "knowledge_graph.json")

# LLM System Prompt for Knowledge Graph Updates
KNOWLEDGE_GRAPH_UPDATE_PROMPT = """You are an intelligent knowledge graph curator. Your job is to maintain a comprehensive, accurate knowledge graph based on conversations.

CURRENT KNOWLEDGE GRAPH:
{current_kg_json}

NEW CONVERSATION:
User: {user_message}
Assistant: {assistant_response}

YOUR TASKS:
1. **Extract Information**: Identify facts, people, dates, preferences, locations, and relationships from the conversation
2. **Check for Duplicates**: Before adding new entities, check if similar entities already exist
   - "Christian Jones" should merge with existing "Christian" if they're the same person
   - "John's mom" should link to existing "Mom" entity
   - Use context clues to determine if entities are the same
3. **Update Existing Entities**: If new information about existing entities is mentioned, update their details
4. **Add New Entities**: Only create new entities if they don't exist in any form
5. **Create Relationships**: Add relationships between entities (family, work, location, etc.)
6. **Maintain Consistency**: Ensure all entity IDs in relationships reference valid entities

ENTITY TYPES:
- person: People mentioned (family, friends, colleagues)
- date: Important dates (birthdays, anniversaries, deadlines)
- fact: General facts and information
- preference: User preferences (favorite foods, hobbies, likes/dislikes)
- location: Places (cities, addresses, venues)
- relationship: Should NOT be used - use the relationships array instead

RELATIONSHIP TYPES:
- family: Family relationships (parent, sibling, child, spouse)
- work: Professional relationships (colleague, manager, client)
- location: Location associations (lives in, works at, from)
- interest: Shared interests or activities
- other: Any other type of relationship

KNOWLEDGE GRAPH STRUCTURE:
{{
  "version": "1.0",
  "last_updated": "ISO timestamp",
  "entities": [
    {{
      "id": integer (unique ID),
      "entity_type": "person|date|fact|preference|location",
      "name": "Entity Name",
      "value": "Primary value or descriptor",
      "description": "Additional context (optional)",
      "confidence": 0.0-1.0,
      "created_at": "ISO timestamp",
      "last_mentioned": "ISO timestamp",
      "mention_count": integer
    }}
  ],
  "relationships": [
    {{
      "id": integer (unique ID),
      "entity1_id": integer (id of first entity),
      "entity2_id": integer (id of second entity),
      "relationship_type": "family|work|location|interest|other",
      "description": "Description of relationship",
      "confidence": 0.0-1.0,
      "created_at": "ISO timestamp"
    }}
  ]
}}

IMPORTANT RULES:
1. Keep all existing entities unless they are clear duplicates
2. When merging duplicates, keep the most complete/informative version
3. Increment mention_count for updated entities
4. Update last_mentioned timestamp for referenced entities
5. Preserve entity IDs when updating (don't create new IDs for existing entities)
6. Only create new entity IDs for genuinely new entities
7. Set confidence based on how certain you are (explicit facts = 0.95, implied = 0.7-0.8, guessed = 0.5-0.6)
8. Return the COMPLETE updated knowledge graph (not just changes)

Return ONLY valid JSON with the complete updated knowledge graph. No explanations, no markdown code blocks, just the JSON."""


def load_knowledge_graph() -> dict:
    """
    Load the knowledge graph from JSON file.

    Returns:
        Knowledge graph dictionary, or empty structure if file doesn't exist
    """
    if not os.path.exists(KG_FILE_PATH):
        # Return empty structure
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "entities": [],
            "relationships": []
        }

    try:
        with open(KG_FILE_PATH, 'r', encoding='utf-8') as f:
            kg = json.load(f)
            return kg
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading knowledge graph: {e}")
        # Return empty structure on error
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "entities": [],
            "relationships": []
        }


def save_knowledge_graph(kg: dict) -> bool:
    """
    Save the knowledge graph to JSON file atomically.

    Args:
        kg: Knowledge graph dictionary

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Update timestamp
        kg["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Write to temporary file first (atomic save)
        temp_path = KG_FILE_PATH + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(kg, f, indent=2, ensure_ascii=False)

        # Atomic rename
        os.replace(temp_path, KG_FILE_PATH)
        return True

    except (IOError, OSError) as e:
        print(f"Error saving knowledge graph: {e}")
        return False


def validate_kg_structure(kg: dict) -> bool:
    """
    Validate that knowledge graph has correct structure.

    Args:
        kg: Knowledge graph dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    # Check required top-level keys
    required_keys = {"version", "last_updated", "entities", "relationships"}
    if not all(key in kg for key in required_keys):
        print("Missing required keys in knowledge graph")
        return False

    # Check entities is a list
    if not isinstance(kg["entities"], list):
        print("Entities must be a list")
        return False

    # Check relationships is a list
    if not isinstance(kg["relationships"], list):
        print("Relationships must be a list")
        return False

    # Validate each entity has required fields
    for entity in kg["entities"]:
        required_entity_keys = {"id", "entity_type", "name", "value"}
        if not all(key in entity for key in required_entity_keys):
            print(f"Entity missing required keys: {entity}")
            return False

    # Validate each relationship has required fields
    for rel in kg["relationships"]:
        required_rel_keys = {"id", "entity1_id", "entity2_id", "relationship_type"}
        if not all(key in rel for key in required_rel_keys):
            print(f"Relationship missing required keys: {rel}")
            return False

    return True


def validate_kg_update(old_kg: dict, new_kg: dict) -> bool:
    """
    Validate that the updated knowledge graph is reasonable.

    Checks:
    - Structure is valid
    - No mass deletion of entities (>20% loss is suspicious)
    - All relationship entity IDs reference valid entities

    Args:
        old_kg: Previous knowledge graph
        new_kg: Updated knowledge graph

    Returns:
        True if update is valid, False otherwise
    """
    # Check structure
    if not validate_kg_structure(new_kg):
        return False

    # Check for mass deletion (suspicious if >20% of entities disappeared)
    old_entity_count = len(old_kg.get("entities", []))
    new_entity_count = len(new_kg.get("entities", []))

    if old_entity_count > 5:  # Only check if we have a reasonable number of entities
        if new_entity_count < old_entity_count * 0.8:
            print(f"Warning: Mass deletion detected ({old_entity_count} → {new_entity_count} entities)")
            return False

    # Check that all relationship entity IDs reference valid entities
    entity_ids = {e["id"] for e in new_kg["entities"]}
    for rel in new_kg["relationships"]:
        if rel["entity1_id"] not in entity_ids:
            print(f"Invalid relationship: entity1_id {rel['entity1_id']} not found")
            return False
        if rel["entity2_id"] not in entity_ids:
            print(f"Invalid relationship: entity2_id {rel['entity2_id']} not found")
            return False

    return True


def update_knowledge_graph_with_llm(
    user_message: str,
    assistant_response: str,
    client: Any,
    current_kg: Optional[dict] = None
) -> Optional[dict]:
    """
    Use LLM to intelligently update the knowledge graph.

    This is the core function that:
    1. Loads current knowledge graph
    2. Passes it to LLM with new conversation
    3. LLM returns updated graph with semantic deduplication
    4. Validates and saves the update

    Args:
        user_message: User's message
        assistant_response: Assistant's response
        client: Groq client instance
        current_kg: Optional current knowledge graph (will load if not provided)

    Returns:
        Updated knowledge graph dict, or None if update failed
    """
    # Load current knowledge graph if not provided
    if current_kg is None:
        current_kg = load_knowledge_graph()

    # Serialize current KG to JSON for prompt
    current_kg_json = json.dumps(current_kg, indent=2)

    # Build prompt
    prompt = KNOWLEDGE_GRAPH_UPDATE_PROMPT.format(
        current_kg_json=current_kg_json,
        user_message=user_message,
        assistant_response=assistant_response
    )

    try:
        # Call LLM
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt}
            ],
            model=config.GROQ_MODEL,
            temperature=0.1,  # Low temperature for consistent extraction
            max_tokens=8000   # Allow for large knowledge graphs
        )

        # Parse response
        response_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            # Find the first and last ```
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        # Parse JSON
        updated_kg = json.loads(response_text)

        # Validate update
        if not validate_kg_update(current_kg, updated_kg):
            print("Knowledge graph update validation failed, keeping old version")
            return None

        # Save updated graph
        if save_knowledge_graph(updated_kg):
            return updated_kg
        else:
            print("Failed to save knowledge graph")
            return None

    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response as JSON: {e}")
        print(f"Response: {response_text[:500]}")
        return None
    except Exception as e:
        print(f"Error updating knowledge graph with LLM: {e}")
        return None


def build_context_from_kg(kg: Optional[dict] = None, max_entities: int = 30, min_confidence: float = 0.5) -> str:
    """
    Build context string from knowledge graph for injection into prompts.

    Args:
        kg: Knowledge graph dict (will load if not provided)
        max_entities: Maximum number of entities to include
        min_confidence: Minimum confidence threshold

    Returns:
        Formatted context string
    """
    if kg is None:
        kg = load_knowledge_graph()

    entities = kg.get("entities", [])
    relationships = kg.get("relationships", [])

    # Filter by confidence
    entities = [e for e in entities if e.get("confidence", 1.0) >= min_confidence]

    if not entities:
        return ""

    # Sort by mention count and recency
    entities = sorted(
        entities,
        key=lambda e: (e.get("mention_count", 0), e.get("last_mentioned", "")),
        reverse=True
    )

    # Limit to max_entities
    entities = entities[:max_entities]

    # Group by type
    by_type = {}
    for entity in entities:
        entity_type = entity.get("entity_type", "other")
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append(entity)

    # Type labels
    type_labels = {
        "person": "## People",
        "date": "## Important Dates",
        "fact": "## Facts",
        "preference": "## Preferences",
        "location": "## Locations"
    }

    # Build context
    context_parts = ["# Knowledge Graph Context\n"]

    for entity_type, label in type_labels.items():
        if entity_type in by_type:
            context_parts.append(f"\n{label}")
            for entity in by_type[entity_type]:
                name = entity.get("name", "")
                value = entity.get("value", "")
                description = entity.get("description", "")

                if description:
                    context_parts.append(f"- **{name}**: {value} ({description})")
                else:
                    context_parts.append(f"- **{name}**: {value}")

    # Add relationships if any
    if relationships:
        context_parts.append("\n## Relationships")
        context_parts.append("NOTE: Use these relationships to infer indirect connections (e.g., parent→child→grandchild)")

        # Create entity ID to name mapping for ALL entities (not just filtered ones)
        all_entities = kg.get("entities", [])
        entity_map = {e["id"]: e["name"] for e in all_entities}

        # Show ALL relationships (don't limit to 10) for proper reasoning
        for rel in relationships:
            entity1_name = entity_map.get(rel["entity1_id"], "Unknown")
            entity2_name = entity_map.get(rel["entity2_id"], "Unknown")
            rel_type = rel.get("relationship_type", "related to")
            description = rel.get("description", "")

            if description:
                context_parts.append(f"- {entity1_name} {description} {entity2_name} ({rel_type})")
            else:
                context_parts.append(f"- {entity1_name} ↔ {entity2_name} ({rel_type})")

    return "\n".join(context_parts)
