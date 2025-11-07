"""
Migrate Knowledge Graph to Use Type-Specific Attributes

This script migrates the existing knowledge graph to use type-specific attributes
instead of separate date entities for birthdates and relationships for simple properties.

Migrations:
1. Move birthdates from separate date entities to person.birthdate attribute
2. Add gender attribute to person entities based on value/description
3. Add recurring: true to anniversary/birthday date entities
4. Add category to fact entities
5. Remove birthdate relationships (now redundant)
6. Remove separate birthdate entities (now redundant)
"""

from knowledge_graph_manager import load_knowledge_graph, save_knowledge_graph, validate_kg_structure
from datetime import datetime, timezone

def migrate_birthdates_to_attributes(kg: dict) -> dict:
    """
    Move birthdates from separate date entities to person.birthdate attributes.

    Current: Person entity + separate date entity with relationship
    New: Person entity with birthdate attribute
    """
    # Build mapping of person_id -> birthdate from relationships
    birthdate_map = {}

    # Find all birthdate relationships
    for rel in kg.get("relationships", []):
        if rel.get("description") == "birthdate":
            person_id = rel["entity1_id"]
            date_entity_id = rel["entity2_id"]

            # Find the date entity
            for entity in kg.get("entities", []):
                if entity["id"] == date_entity_id:
                    birthdate_value = entity["value"]
                    birthdate_map[person_id] = birthdate_value
                    break

    print(f"Found {len(birthdate_map)} birthdates to migrate")

    # Add birthdate attribute to person entities
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "person" and entity["id"] in birthdate_map:
            entity["birthdate"] = birthdate_map[entity["id"]]
            print(f"  Added birthdate to {entity['name']}: {entity['birthdate']}")

    return kg


def add_gender_attributes(kg: dict) -> dict:
    """
    Add gender attribute to person entities based on value/description.
    """
    # Mapping of person IDs to likely gender based on knowledge
    gender_map = {
        1: "male",    # James Weaver
        3: "female",  # Julie Weaver
        7: "female",  # Lori Hutchins (daughter)
        8: "female",  # Kelli Jones (daughter)
        9: "male",    # Christian Jones (spouse of daughter, male name)
        10: "male",   # Levi Jones (son)
        11: "male",   # Oliver Jones (son)
        12: "male",   # Marty Hutchins (spouse of daughter, male name)
        13: "male",   # Kaleb Hutchins (son)
        14: "female", # Jillian Hutchins (daughter)
    }

    for entity in kg.get("entities", []):
        if entity["entity_type"] == "person" and entity["id"] in gender_map:
            entity["gender"] = gender_map[entity["id"]]
            print(f"  Added gender to {entity['name']}: {entity['gender']}")

    return kg


def add_date_type_specific_attrs(kg: dict) -> dict:
    """
    Add type-specific attributes to date entities.
    """
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "date":
            name = entity.get("name", "").lower()

            # Check if it's a recurring event
            if "anniversary" in name or "birthday" in name:
                entity["recurring"] = True
                entity["importance"] = "high"
                entity["event_type"] = "anniversary" if "anniversary" in name else "birthday"
                print(f"  Added recurring attrs to {entity['name']}")

    return kg


def add_fact_categories(kg: dict) -> dict:
    """
    Add category to fact entities based on content.
    """
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "fact":
            name = entity.get("name", "").lower()
            description = entity.get("description", "").lower()

            # Infer category from content
            if "child" in name or "grandchild" in name:
                entity["category"] = "family"
            elif "cousin" in name:
                entity["category"] = "family"
            else:
                entity["category"] = "general"

            entity["verified"] = True
            entity["source"] = "conversation"
            print(f"  Added category to {entity['name']}: {entity['category']}")

    return kg


def remove_birthdate_relationships(kg: dict) -> dict:
    """
    Remove relationships that link people to birthdate entities (now redundant).
    """
    original_count = len(kg.get("relationships", []))

    kg["relationships"] = [
        rel for rel in kg.get("relationships", [])
        if rel.get("description") != "birthdate"
    ]

    removed = original_count - len(kg["relationships"])
    print(f"Removed {removed} birthdate relationships (now redundant)")

    return kg


def remove_birthdate_entities(kg: dict) -> dict:
    """
    Remove separate date entities for birthdates (now stored as person attributes).
    Keep important dates like anniversaries.
    """
    original_count = len(kg.get("entities", []))

    # Keep entities that are NOT individual birthdates
    kg["entities"] = [
        entity for entity in kg.get("entities", [])
        if not (entity["entity_type"] == "date" and "birthdate" in entity.get("name", "").lower())
    ]

    removed = original_count - len(kg["entities"])
    print(f"Removed {removed} birthdate entities (now person attributes)")

    return kg


def show_migration_summary(kg: dict):
    """
    Show summary of migrated knowledge graph.
    """
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)

    # Count entities by type
    by_type = {}
    for entity in kg.get("entities", []):
        entity_type = entity["entity_type"]
        by_type[entity_type] = by_type.get(entity_type, 0) + 1

    print(f"\nEntities by type:")
    for entity_type, count in by_type.items():
        print(f"  {entity_type}: {count}")

    print(f"\nRelationships: {len(kg.get('relationships', []))}")

    # Show people with birthdates
    print(f"\nPeople with birthdate attribute:")
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "person" and "birthdate" in entity:
            print(f"  {entity['name']}: {entity['birthdate']} ({entity.get('gender', 'unknown')})")

    # Show dates with type-specific attrs
    print(f"\nDate entities with type-specific attributes:")
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "date":
            attrs = []
            if "recurring" in entity:
                attrs.append(f"recurring={entity['recurring']}")
            if "importance" in entity:
                attrs.append(f"importance={entity['importance']}")
            if "event_type" in entity:
                attrs.append(f"type={entity['event_type']}")

            if attrs:
                print(f"  {entity['name']}: {', '.join(attrs)}")


def main():
    """
    Main migration function.
    """
    print("=" * 60)
    print("MIGRATING TO TYPE-SPECIFIC ATTRIBUTES")
    print("=" * 60)

    # Load current KG
    print("\n1. Loading knowledge graph...")
    kg = load_knowledge_graph()
    print(f"   Loaded {len(kg.get('entities', []))} entities, {len(kg.get('relationships', []))} relationships")

    # Backup original
    print("\n2. Creating backup...")
    import shutil
    from knowledge_graph_manager import KG_FILE_PATH
    backup_path = KG_FILE_PATH + ".backup"
    shutil.copy(KG_FILE_PATH, backup_path)
    print(f"   Backup saved to {backup_path}")

    # Apply migrations
    print("\n3. Migrating birthdates to person attributes...")
    kg = migrate_birthdates_to_attributes(kg)

    print("\n4. Adding gender attributes...")
    kg = add_gender_attributes(kg)

    print("\n5. Adding date type-specific attributes...")
    kg = add_date_type_specific_attrs(kg)

    print("\n6. Adding fact categories...")
    kg = add_fact_categories(kg)

    print("\n7. Removing birthdate relationships...")
    kg = remove_birthdate_relationships(kg)

    print("\n8. Removing birthdate entities...")
    kg = remove_birthdate_entities(kg)

    # Validate
    print("\n9. Validating migrated knowledge graph...")
    if validate_kg_structure(kg):
        print("   ✓ Validation passed")
    else:
        print("   ✗ Validation failed - NOT saving")
        return

    # Save
    print("\n10. Saving migrated knowledge graph...")
    if save_knowledge_graph(kg):
        print("   ✓ Saved successfully")
    else:
        print("   ✗ Save failed")
        return

    # Show summary
    show_migration_summary(kg)

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"\nBackup saved at: {backup_path}")
    print("If anything went wrong, restore with:")
    print(f"  cp {backup_path} {KG_FILE_PATH}")


if __name__ == "__main__":
    main()
