"""
Test and Showcase Type-Specific Attributes

This script demonstrates the improved knowledge graph structure with
type-specific attributes.
"""

from knowledge_graph_manager import load_knowledge_graph, build_context_from_kg
import json

def show_entity_examples():
    """
    Show examples of entities with type-specific attributes.
    """
    kg = load_knowledge_graph()

    print("=" * 60)
    print("ENTITY EXAMPLES WITH TYPE-SPECIFIC ATTRIBUTES")
    print("=" * 60)

    # Example 1: Person with birthdate and gender
    print("\n1. PERSON ENTITY (with birthdate and gender):")
    print("-" * 60)
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "person" and entity["id"] == 8:  # Kelli Jones
            print(json.dumps(entity, indent=2))
            break

    # Example 2: Another person
    print("\n2. PERSON ENTITY (James Weaver):")
    print("-" * 60)
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "person" and entity["id"] == 1:  # James
            print(json.dumps(entity, indent=2))
            break

    # Example 3: Date entity
    print("\n3. DATE ENTITY:")
    print("-" * 60)
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "date":
            print(json.dumps(entity, indent=2))
            break

    # Example 4: Fact entity with category
    print("\n4. FACT ENTITY (with category):")
    print("-" * 60)
    for entity in kg.get("entities", []):
        if entity["entity_type"] == "fact":
            print(json.dumps(entity, indent=2))
            break


def test_attribute_queries():
    """
    Test querying entities by type-specific attributes.
    """
    kg = load_knowledge_graph()

    print("\n" + "=" * 60)
    print("TESTING ATTRIBUTE QUERIES")
    print("=" * 60)

    # Test 1: Find all males
    print("\n1. All male people:")
    males = [e for e in kg.get("entities", [])
             if e.get("entity_type") == "person" and e.get("gender") == "male"]
    for person in males:
        print(f"   - {person['name']} (birthdate: {person.get('birthdate', 'unknown')})")

    # Test 2: Find all females
    print("\n2. All female people:")
    females = [e for e in kg.get("entities", [])
               if e.get("entity_type") == "person" and e.get("gender") == "female"]
    for person in females:
        print(f"   - {person['name']} (birthdate: {person.get('birthdate', 'unknown')})")

    # Test 3: Find people born in specific year
    print("\n3. People born in 2004 or later (children):")
    children = [e for e in kg.get("entities", [])
                if e.get("entity_type") == "person" and
                e.get("birthdate", "") >= "2004-01-01"]
    children.sort(key=lambda x: x.get("birthdate", ""))
    for person in children:
        age = 2025 - int(person.get("birthdate", "0000")[:4])
        print(f"   - {person['name']}: born {person.get('birthdate')} (age ~{age})")

    # Test 4: Find all facts about family
    print("\n4. Facts categorized as 'family':")
    family_facts = [e for e in kg.get("entities", [])
                    if e.get("entity_type") == "fact" and e.get("category") == "family"]
    for fact in family_facts:
        print(f"   - {fact['name']}: {fact['value']}")


def show_comparison():
    """
    Show comparison of old vs new structure.
    """
    print("\n" + "=" * 60)
    print("BEFORE vs AFTER COMPARISON")
    print("=" * 60)

    print("\nBEFORE (old structure - separate entities):")
    print("-" * 60)
    old_structure = """
{
  "entities": [
    {"id": 8, "entity_type": "person", "name": "Kelli Jones", "value": "daughter"},
    {"id": 18, "entity_type": "date", "name": "Kelli Jones birthdate", "value": "1995-08-22"}
  ],
  "relationships": [
    {"entity1_id": 8, "entity2_id": 18, "description": "birthdate"}
  ]
}

Problems:
- Birthdate scattered across 3 places (person, date entity, relationship)
- Hard to query "Who was born in 1995?"
- Gender information not stored anywhere
- Extra entities and relationships for simple attributes
"""
    print(old_structure)

    print("\nAFTER (new structure - type-specific attributes):")
    print("-" * 60)
    new_structure = """
{
  "entities": [
    {
      "id": 8,
      "entity_type": "person",
      "name": "Kelli Jones",
      "value": "daughter",
      "birthdate": "1995-08-22",  ← Now an attribute
      "gender": "female"          ← Now an attribute
    }
  ],
  "relationships": []  ← No birthdate relationship needed
}

Benefits:
✓ All person info in one place
✓ Easy to query "Who was born in 1995?" → filter by birthdate
✓ Gender explicitly stored and queryable
✓ Cleaner, more efficient structure
✓ Fewer entities and relationships
"""
    print(new_structure)


def show_context_output():
    """
    Show how the knowledge graph context looks now.
    """
    print("\n" + "=" * 60)
    print("KNOWLEDGE GRAPH CONTEXT (for LLM)")
    print("=" * 60)

    context = build_context_from_kg()
    print(context)


def show_statistics():
    """
    Show statistics about the knowledge graph.
    """
    kg = load_knowledge_graph()

    print("\n" + "=" * 60)
    print("KNOWLEDGE GRAPH STATISTICS")
    print("=" * 60)

    total_entities = len(kg.get("entities", []))
    total_relationships = len(kg.get("relationships", []))

    print(f"\nTotal entities: {total_entities}")
    print(f"Total relationships: {total_relationships}")

    # Count by type
    by_type = {}
    for entity in kg.get("entities", []):
        entity_type = entity["entity_type"]
        by_type[entity_type] = by_type.get(entity_type, 0) + 1

    print(f"\nEntities by type:")
    for entity_type, count in by_type.items():
        print(f"  {entity_type}: {count}")

    # Count people with type-specific attributes
    people = [e for e in kg.get("entities", []) if e.get("entity_type") == "person"]
    with_birthdate = len([p for p in people if "birthdate" in p])
    with_gender = len([p for p in people if "gender" in p])

    print(f"\nPeople with type-specific attributes:")
    print(f"  With birthdate: {with_birthdate}/{len(people)}")
    print(f"  With gender: {with_gender}/{len(people)}")

    # Relationship types
    rel_types = {}
    for rel in kg.get("relationships", []):
        rel_type = rel.get("relationship_type", "unknown")
        rel_types[rel_type] = rel_types.get(rel_type, 0) + 1

    print(f"\nRelationships by type:")
    for rel_type, count in rel_types.items():
        print(f"  {rel_type}: {count}")


def main():
    """
    Run all tests and examples.
    """
    show_entity_examples()
    test_attribute_queries()
    show_comparison()
    show_statistics()
    show_context_output()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
