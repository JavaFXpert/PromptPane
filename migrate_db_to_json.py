"""
Migrate Database Entities to JSON Knowledge Graph

This script exports all entities and relationships from the SQLite database
to the new JSON-based knowledge graph format.

Run this once to migrate from the old database-only approach to the new
JSON-based LLM-curated knowledge graph.
"""

import json
from datetime import datetime, timezone
import db
from knowledge_graph_manager import KG_FILE_PATH, save_knowledge_graph


def migrate_entities_to_json():
    """Export all entities and relationships from database to JSON"""

    print("Migrating entities from database to JSON knowledge graph...")

    # Get all entities from database (globally)
    db_entities = db.get_entities()

    print(f"Found {len(db_entities)} entities in database")

    # Convert to JSON format
    json_entities = []
    for entity in db_entities:
        json_entity = {
            "id": entity['id'],  # Keep as integer for compatibility with UI routes
            "entity_type": entity["entity_type"],
            "name": entity["name"],
            "value": entity["value"],
            "description": entity.get("description", ""),
            "confidence": entity.get("confidence", 1.0),
            "created_at": entity.get("created_at", datetime.now(timezone.utc).isoformat()),
            "last_mentioned": entity.get("last_mentioned", datetime.now(timezone.utc).isoformat()),
            "mention_count": entity.get("mention_count", 1)
        }
        json_entities.append(json_entity)

    # Get all relationships
    # Note: We need to get relationships for all entities
    json_relationships = []
    processed_rel_ids = set()

    for entity in db_entities:
        entity_id = entity["id"]
        rels = db.get_relationships(entity_id)

        for rel in rels:
            # Skip if we've already processed this relationship
            # (relationships are bidirectional)
            if rel["id"] in processed_rel_ids:
                continue

            processed_rel_ids.add(rel["id"])

            json_rel = {
                "id": rel['id'],  # Keep as integer
                "entity1_id": rel['entity1_id'],  # Keep as integer
                "entity2_id": rel['entity2_id'],  # Keep as integer
                "relationship_type": rel.get("relationship_type", "other"),
                "description": rel.get("description", ""),
                "confidence": rel.get("confidence", 1.0),
                "created_at": rel.get("created_at", datetime.now(timezone.utc).isoformat())
            }
            json_relationships.append(json_rel)

    print(f"Found {len(json_relationships)} relationships in database")

    # Create knowledge graph structure
    kg = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "entities": json_entities,
        "relationships": json_relationships
    }

    # Save to file
    if save_knowledge_graph(kg):
        print(f"\n✓ Successfully migrated to {KG_FILE_PATH}")
        print(f"  - {len(json_entities)} entities")
        print(f"  - {len(json_relationships)} relationships")
    else:
        print("\n✗ Failed to save knowledge graph")
        return False

    # Show sample of what was migrated
    print("\nSample entities:")
    for entity in json_entities[:5]:
        print(f"  - {entity['name']} ({entity['entity_type']}): {entity['value']}")

    if json_relationships:
        print("\nSample relationships:")
        for rel in json_relationships[:3]:
            print(f"  - {rel['entity1_id']} → {rel['entity2_id']} ({rel['relationship_type']})")

    return True


if __name__ == "__main__":
    success = migrate_entities_to_json()
    if success:
        print("\nMigration complete!")
        print("\nNext steps:")
        print("1. Verify the knowledge_graph.json file looks correct")
        print("2. The database will remain as a cache, but JSON is now the source of truth")
        print("3. The LLM will update the JSON file going forward")
    else:
        print("\nMigration failed. Please check errors above.")
