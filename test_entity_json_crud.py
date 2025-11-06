"""
Test script to verify entity CRUD operations work with JSON
"""

from knowledge_graph_manager import load_knowledge_graph, save_knowledge_graph
import json

print("=" * 60)
print("TEST: Entity CRUD Operations with JSON")
print("=" * 60)

# Test 1: Load knowledge graph
print("\n1. Loading knowledge graph...")
kg = load_knowledge_graph()
print(f"   ✓ Loaded {len(kg.get('entities', []))} entities")

# Show current entities
print("\n   Current entities:")
for e in kg.get("entities", []):
    print(f"   - ID {e['id']}: {e['name']} ({e['entity_type']})")

# Test 2: Find an entity by ID
print("\n2. Testing entity lookup by ID...")
test_entity_id = kg.get("entities", [])[0]["id"] if kg.get("entities") else None
if test_entity_id:
    entity = None
    for e in kg.get("entities", []):
        if e["id"] == test_entity_id:
            entity = e
            break
    if entity:
        print(f"   ✓ Found entity {test_entity_id}: {entity['name']}")
    else:
        print(f"   ✗ Failed to find entity {test_entity_id}")
else:
    print("   ⚠ No entities to test with")

# Test 3: Update an entity
print("\n3. Testing entity update...")
if test_entity_id and entity:
    original_name = entity["name"]
    entity["name"] = f"{original_name} (UPDATED)"
    entity["description"] = "This entity was updated by test script"

    if save_knowledge_graph(kg):
        print(f"   ✓ Updated entity {test_entity_id}")

        # Reload and verify
        kg_reloaded = load_knowledge_graph()
        updated_entity = None
        for e in kg_reloaded.get("entities", []):
            if e["id"] == test_entity_id:
                updated_entity = e
                break

        if updated_entity and updated_entity["name"] == f"{original_name} (UPDATED)":
            print(f"   ✓ Verified update persisted: {updated_entity['name']}")

            # Restore original
            updated_entity["name"] = original_name
            updated_entity["description"] = entity.get("description", "")
            save_knowledge_graph(kg_reloaded)
            print(f"   ✓ Restored original name")
        else:
            print(f"   ✗ Update did not persist correctly")
    else:
        print(f"   ✗ Failed to save updated entity")
else:
    print("   ⚠ No entity to update")

# Test 4: Add a test entity
print("\n4. Testing entity creation...")
kg = load_knowledge_graph()
test_entity = {
    "id": 9999,  # Use a high ID that won't conflict
    "entity_type": "fact",
    "name": "Test Entity",
    "value": "Test Value",
    "description": "Created by test script",
    "confidence": 0.95,
    "created_at": "2025-11-06T00:00:00+00:00",
    "last_mentioned": "2025-11-06T00:00:00+00:00",
    "mention_count": 1
}

kg["entities"].append(test_entity)

if save_knowledge_graph(kg):
    print(f"   ✓ Added test entity {test_entity['id']}")

    # Reload and verify
    kg_reloaded = load_knowledge_graph()
    found = False
    for e in kg_reloaded.get("entities", []):
        if e["id"] == 9999:
            found = True
            break

    if found:
        print(f"   ✓ Verified test entity persisted")
    else:
        print(f"   ✗ Test entity did not persist")
else:
    print(f"   ✗ Failed to save test entity")

# Test 5: Delete the test entity
print("\n5. Testing entity deletion...")
kg = load_knowledge_graph()
entities_before = len(kg.get("entities", []))
kg["entities"] = [e for e in kg.get("entities", []) if e["id"] != 9999]
entities_after = len(kg.get("entities", []))

if save_knowledge_graph(kg):
    print(f"   ✓ Deleted test entity")
    print(f"   ✓ Entities before: {entities_before}, after: {entities_after}")

    # Reload and verify
    kg_reloaded = load_knowledge_graph()
    found = False
    for e in kg_reloaded.get("entities", []):
        if e["id"] == 9999:
            found = True
            break

    if not found:
        print(f"   ✓ Verified test entity was deleted")
    else:
        print(f"   ✗ Test entity still exists after deletion")
else:
    print(f"   ✗ Failed to save after deletion")

print("\n" + "=" * 60)
print("TESTS COMPLETE")
print("=" * 60)
