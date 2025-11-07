"""
Migrate Remaining Date Attributes

This script completes the migration to type-specific attributes by:
1. Adding Julie Weaver's birthdate as an attribute (from separate date entity)
2. Removing the redundant "Julie birth date" entity
3. Adding type-specific attributes to the "Marriage date" entity
"""

from knowledge_graph_manager import load_knowledge_graph, save_knowledge_graph, validate_kg_structure
import shutil
from knowledge_graph_manager import KG_FILE_PATH


def migrate_julie_birthdate(kg: dict) -> dict:
    """
    Move Julie's birthdate from separate entity to person attribute.
    """
    # Find Julie Weaver entity
    julie_entity = None
    for entity in kg.get("entities", []):
        if entity["id"] == 3 and entity["name"] == "Julie Weaver":
            julie_entity = entity
            break

    if julie_entity:
        # Add birthdate attribute
        julie_entity["birthdate"] = "1955-10-13"
        print(f"  ✓ Added birthdate to Julie Weaver: 1955-10-13")
    else:
        print(f"  ✗ Julie Weaver entity not found")

    return kg


def remove_julie_birthdate_entity(kg: dict) -> dict:
    """
    Remove the separate "Julie birth date" entity (now redundant).
    """
    original_count = len(kg.get("entities", []))

    # Remove the Julie birth date entity (id: 4)
    kg["entities"] = [
        entity for entity in kg.get("entities", [])
        if not (entity["id"] == 4 and entity["name"] == "Julie birth date")
    ]

    removed = original_count - len(kg["entities"])
    if removed > 0:
        print(f"  ✓ Removed Julie birth date entity (now an attribute)")
    else:
        print(f"  ✗ Julie birth date entity not found")

    return kg


def add_marriage_date_attributes(kg: dict) -> dict:
    """
    Add type-specific attributes to the Marriage date entity.
    """
    # Find Marriage date entity
    for entity in kg.get("entities", []):
        if entity["id"] == 5 and entity["name"] == "Marriage date":
            # Add type-specific attributes for recurring anniversary
            entity["recurring"] = True
            entity["importance"] = "high"
            entity["event_type"] = "anniversary"
            print(f"  ✓ Added type-specific attributes to Marriage date")
            print(f"    - recurring: true")
            print(f"    - importance: high")
            print(f"    - event_type: anniversary")
            break

    return kg


def show_summary(kg: dict):
    """
    Show summary of migration.
    """
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)

    # Show Julie with birthdate
    print("\nJulie Weaver entity:")
    for entity in kg.get("entities", []):
        if entity["id"] == 3:
            print(f"  Name: {entity['name']}")
            print(f"  Birthdate: {entity.get('birthdate', 'NOT SET')}")
            print(f"  Gender: {entity.get('gender', 'NOT SET')}")
            break

    # Show Marriage date entity
    print("\nMarriage date entity:")
    for entity in kg.get("entities", []):
        if entity["id"] == 5:
            print(f"  Name: {entity['name']}")
            print(f"  Value: {entity['value']}")
            print(f"  Recurring: {entity.get('recurring', 'NOT SET')}")
            print(f"  Importance: {entity.get('importance', 'NOT SET')}")
            print(f"  Event type: {entity.get('event_type', 'NOT SET')}")
            break

    # Show total counts
    print(f"\nTotal entities: {len(kg.get('entities', []))}")
    print(f"Total relationships: {len(kg.get('relationships', []))}")


def main():
    """
    Main migration function.
    """
    print("=" * 60)
    print("MIGRATING REMAINING DATE ATTRIBUTES")
    print("=" * 60)

    # Load current KG
    print("\n1. Loading knowledge graph...")
    kg = load_knowledge_graph()
    print(f"   Loaded {len(kg.get('entities', []))} entities, {len(kg.get('relationships', []))} relationships")

    # Backup original
    print("\n2. Creating backup...")
    backup_path = KG_FILE_PATH + ".backup2"
    shutil.copy(KG_FILE_PATH, backup_path)
    print(f"   Backup saved to {backup_path}")

    # Apply migrations
    print("\n3. Adding Julie's birthdate attribute...")
    kg = migrate_julie_birthdate(kg)

    print("\n4. Removing Julie birth date entity...")
    kg = remove_julie_birthdate_entity(kg)

    print("\n5. Adding type-specific attributes to Marriage date...")
    kg = add_marriage_date_attributes(kg)

    # Validate
    print("\n6. Validating migrated knowledge graph...")
    if validate_kg_structure(kg):
        print("   ✓ Validation passed")
    else:
        print("   ✗ Validation failed - NOT saving")
        return

    # Save
    print("\n7. Saving migrated knowledge graph...")
    if save_knowledge_graph(kg):
        print("   ✓ Saved successfully")
    else:
        print("   ✗ Save failed")
        return

    # Show summary
    show_summary(kg)

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"\nBackup saved at: {backup_path}")
    print("If anything went wrong, restore with:")
    print(f"  cp {backup_path} {KG_FILE_PATH}")


if __name__ == "__main__":
    main()
