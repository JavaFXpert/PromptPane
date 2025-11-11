"""
Learning Objectives Manager

Handles creation, storage, and LLM-driven management of hierarchical learning objectives.
Supports recursive decomposition and automatic mastery tracking.
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from groq import Groq

logger = logging.getLogger(__name__)

# File path for learning objectives storage
OBJECTIVES_FILE_PATH = "learning_objectives.json"

# Maximum decomposition depth to prevent infinite recursion
MAX_DECOMPOSITION_DEPTH = 4

# Mastery levels
MASTERY_LEVELS = ["not_started", "learning", "practiced", "mastered"]

# ============================================================================
# Core Load/Save Functions
# ============================================================================

def load_learning_objectives() -> dict:
    """
    Load learning objectives from JSON file.

    Returns:
        dict: Learning objectives structure with active_objective only
    """
    if not os.path.exists(OBJECTIVES_FILE_PATH):
        logger.info("Learning objectives file not found, creating new one")
        return {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "active_objective": None
        }

    try:
        with open(OBJECTIVES_FILE_PATH, 'r', encoding='utf-8') as f:
            objectives = json.load(f)
            logger.info("Loaded learning objectives successfully")
            return objectives
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse learning objectives JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading learning objectives: {e}")
        raise


def save_learning_objectives(objectives: dict) -> bool:
    """
    Save learning objectives to JSON file with atomic write.

    Args:
        objectives: Learning objectives structure

    Returns:
        bool: True if save successful
    """
    try:
        # Update last_updated timestamp
        objectives["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Atomic write: write to temp file first, then rename
        temp_path = OBJECTIVES_FILE_PATH + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(objectives, f, indent=2, ensure_ascii=False)

        # Atomic rename
        os.replace(temp_path, OBJECTIVES_FILE_PATH)
        logger.info("Saved learning objectives successfully")
        return True

    except Exception as e:
        logger.error(f"Error saving learning objectives: {e}")
        raise


# ============================================================================
# Active Objective Management
# ============================================================================

def get_active_objective() -> Optional[dict]:
    """
    Get the currently active learning objective.

    Returns:
        Optional[dict]: Active objective tree or None
    """
    objectives = load_learning_objectives()
    return objectives.get("active_objective")


def set_active_objective(objective: dict, archive_existing: bool = True) -> dict:
    """
    Set a new active learning objective, completely replacing the existing one.

    Args:
        objective: New objective to set as active
        archive_existing: Ignored (kept for API compatibility)

    Returns:
        dict: Updated objectives structure
    """
    objectives = load_learning_objectives()

    # Log if we're replacing an existing objective
    if objectives.get("active_objective"):
        existing = objectives["active_objective"]
        logger.info(f"Replacing existing objective: {existing.get('title')}")

    # Set new active objective (completely replaces old one)
    objectives["active_objective"] = objective
    save_learning_objectives(objectives)

    logger.info(f"Set new active objective: {objective.get('title')}")
    return objectives


def clear_active_objective(archive: bool = True) -> dict:
    """
    Clear the active learning objective.

    Args:
        archive: Ignored (kept for API compatibility)

    Returns:
        dict: Updated objectives structure
    """
    objectives = load_learning_objectives()

    if objectives.get("active_objective"):
        logger.info(f"Clearing objective: {objectives['active_objective'].get('title')}")

    objectives["active_objective"] = None
    save_learning_objectives(objectives)

    logger.info("Cleared active objective")
    return objectives


# ============================================================================
# Tree Traversal Utilities
# ============================================================================

def find_objective_by_id(obj_tree: Optional[dict], target_id: int) -> Optional[dict]:
    """
    Recursively find an objective by ID in the tree.

    Args:
        obj_tree: Root objective or subtree
        target_id: ID to search for

    Returns:
        Optional[dict]: Found objective or None
    """
    if not obj_tree:
        return None

    if obj_tree.get("id") == target_id:
        return obj_tree

    # Search in children
    for child in obj_tree.get("children", []):
        found = find_objective_by_id(child, target_id)
        if found:
            return found

    return None


def get_objective_depth(obj_tree: dict, target_id: int, current_depth: int = 0) -> int:
    """
    Get the depth of an objective in the tree (0 = root).

    Args:
        obj_tree: Root objective
        target_id: ID to find depth for
        current_depth: Current recursion depth

    Returns:
        int: Depth of objective, or -1 if not found
    """
    if obj_tree.get("id") == target_id:
        return current_depth

    for child in obj_tree.get("children", []):
        depth = get_objective_depth(child, target_id, current_depth + 1)
        if depth != -1:
            return depth

    return -1


def update_mastery_by_id(obj_tree: dict, target_id: int, mastery_level: str) -> bool:
    """
    Update mastery level for an objective by ID.

    Args:
        obj_tree: Root objective tree
        target_id: ID of objective to update
        mastery_level: New mastery level

    Returns:
        bool: True if updated successfully
    """
    objective = find_objective_by_id(obj_tree, target_id)

    if not objective:
        logger.warning(f"Objective {target_id} not found for mastery update")
        return False

    if mastery_level not in MASTERY_LEVELS:
        logger.error(f"Invalid mastery level: {mastery_level}")
        return False

    objective["mastery_level"] = mastery_level
    objective["last_updated"] = datetime.now(timezone.utc).isoformat()
    objective["practice_count"] = objective.get("practice_count", 0) + 1

    logger.info(f"Updated mastery for '{objective.get('title')}' to {mastery_level}")
    return True


def get_next_objective_id(obj_tree: Optional[dict]) -> int:
    """
    Get the next available objective ID.

    Args:
        obj_tree: Root objective tree

    Returns:
        int: Next available ID
    """
    if not obj_tree:
        return 1

    max_id = obj_tree.get("id", 0)

    def find_max_id(obj: dict):
        nonlocal max_id
        max_id = max(max_id, obj.get("id", 0))
        for child in obj.get("children", []):
            find_max_id(child)

    find_max_id(obj_tree)
    return max_id + 1


# ============================================================================
# LLM Decomposition
# ============================================================================

def decompose_objective_with_llm(
    title: str,
    description: str,
    client: Groq,
    parent_id: Optional[int] = None,
    current_depth: int = 0
) -> dict:
    """
    Use LLM to create a complete hierarchical learning objective structure in one call.

    Args:
        title: Objective title
        description: Objective description
        client: Groq API client
        parent_id: Parent objective ID (None for root)
        current_depth: Current depth in tree (should be 0 for root)

    Returns:
        dict: Objective with fully decomposed hierarchical children
    """
    logger.info(f"Creating hierarchical learning objectives for: {title}")

    # Prompt for LLM to generate entire hierarchy in one call
    prompt = f"""You are an expert learning coach and instructional designer. Your task is to create a comprehensive hierarchical learning path for the following topic.

Topic: {title}
Description: {description}

IMPORTANT: Before generating the JSON, think deeply about:
1. **Prerequisites & Dependencies**: What foundational knowledge is needed before advanced topics?
2. **Learning Progression**: How should concepts build upon each other naturally?
3. **Cognitive Load**: Are objectives appropriately sized for single learning sessions?
4. **Bloom's Taxonomy**: Progress from knowledge → comprehension → application → analysis
5. **Practical Application**: Include hands-on practice alongside theory
6. **Common Pitfalls**: What do learners typically struggle with? Address these explicitly

PEDAGOGICAL PRINCIPLES:
- Start with "why" and motivation before "what" and "how"
- Include both conceptual understanding AND practical skills
- Ensure each level builds naturally from the previous
- Make leaf objectives concrete and measurable
- Balance breadth (coverage) with depth (mastery)

STRUCTURE REQUIREMENTS:
- Root objective: The main topic
- Each objective: 3-7 carefully chosen sub-objectives
- Maximum depth: 4 levels (root + 3 levels of children)
- Leaf objectives: Atomic and achievable in a single focused lesson (20-60 minutes)
- Each objective needs:
  * title: Concise and specific (5-10 words)
  * description: Clear learning outcome with action verbs (1-2 sentences)

First, mentally map out the learning journey from absolute beginner to proficient practitioner. Consider what a learner needs to know at each stage and how to sequence topics for maximum retention and understanding.

Then, return ONLY valid JSON in this exact format (no markdown, no code blocks, no explanatory text):
{{
  "title": "Learn [Topic]",
  "description": "Master the fundamentals and advanced concepts",
  "children": [
    {{
      "title": "Foundational Concept 1",
      "description": "Description of what learner will master",
      "children": [
        {{
          "title": "Sub-topic 1.1",
          "description": "Specific skill or knowledge",
          "children": [
            {{
              "title": "Atomic Lesson 1.1.1",
              "description": "Single lesson objective",
              "children": []
            }}
          ]
        }}
      ]
    }}
  ]
}}

Now create a thoughtful, well-structured learning path:"""

    try:
        response = client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=15000
        )

        response_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (``` markers)
            response_text = "\n".join(lines[1:-1])
            if response_text.startswith("json"):
                response_text = "\n".join(response_text.split("\n")[1:])

        # Parse JSON
        hierarchy = json.loads(response_text)

        logger.info(f"LLM created hierarchical structure")

        # Recursively convert the hierarchy to our format with IDs and metadata
        objective = convert_hierarchy_to_objectives(hierarchy, parent_id=parent_id)

        # Count total objectives
        total_count = count_objectives(objective)
        logger.info(f"Created {total_count} total objectives in hierarchy")

        return objective

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM hierarchy JSON: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        # Return simple objective without children on error
        return create_objective(title, description, parent_id, [])

    except Exception as e:
        logger.error(f"Error in LLM hierarchy generation: {e}")
        # Return simple objective without children on error
        return create_objective(title, description, parent_id, [])


def convert_hierarchy_to_objectives(node: dict, parent_id: Optional[int] = None, id_counter: List[int] = None) -> dict:
    """
    Recursively convert LLM-generated hierarchy to objective format with IDs and metadata.

    Args:
        node: Node from LLM hierarchy
        parent_id: Parent objective ID
        id_counter: Mutable list with single int for ID generation

    Returns:
        dict: Objective with proper structure
    """
    if id_counter is None:
        id_counter = [1]  # Mutable container for counter

    # Create objective for this node
    obj_id = id_counter[0]
    id_counter[0] += 1

    # Process children recursively
    children = []
    for child_node in node.get("children", []):
        child_obj = convert_hierarchy_to_objectives(child_node, parent_id=obj_id, id_counter=id_counter)
        children.append(child_obj)

    # Create objective with metadata
    objective = {
        "id": obj_id,
        "title": node.get("title", "Untitled"),
        "description": node.get("description", ""),
        "mastery_level": "not_started",
        "parent_id": parent_id,
        "children": children,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "practice_count": 0,
        "notes": ""
    }

    return objective


def count_objectives(objective: dict) -> int:
    """
    Count total number of objectives in tree.

    Args:
        objective: Root objective

    Returns:
        int: Total count
    """
    count = 1
    for child in objective.get("children", []):
        count += count_objectives(child)
    return count


def create_objective(
    title: str,
    description: str,
    parent_id: Optional[int],
    children: List[dict]
) -> dict:
    """
    Create an objective dictionary with proper structure.

    Args:
        title: Objective title
        description: Objective description
        parent_id: Parent objective ID
        children: List of child objectives

    Returns:
        dict: Objective structure
    """
    # Get next ID from active objective tree
    active = get_active_objective()
    next_id = get_next_objective_id(active)

    objective = {
        "id": next_id,
        "title": title,
        "description": description,
        "mastery_level": "not_started",
        "parent_id": parent_id,
        "children": children,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "practice_count": 0,
        "notes": ""
    }

    # Update parent_id for all children
    for child in children:
        child["parent_id"] = next_id

    return objective


# ============================================================================
# LLM Mastery Assessment
# ============================================================================

def update_mastery_with_llm(
    conversation_context: List[Dict[str, str]],
    objective_tree: dict,
    client: Groq
) -> List[Dict[str, Any]]:
    """
    Use LLM to assess learner progress and update mastery levels.

    Args:
        conversation_context: Recent conversation messages
        objective_tree: Current active objective tree
        client: Groq API client

    Returns:
        List[Dict]: List of updates made [{"id": 1, "mastery_level": "learning", "reason": "..."}]
    """
    logger.info("Assessing mastery levels with LLM")

    # Format conversation for prompt
    conversation_text = "\n".join([
        f"{msg['role']}: {msg['content'][:500]}"  # Limit length
        for msg in conversation_context[-6:]  # Last 6 messages
    ])

    # Format objectives for prompt
    objectives_text = format_objectives_for_prompt(objective_tree)

    # Prompt for mastery assessment
    prompt = f"""You are an expert learning coach assessing a learner's progress. Based on this conversation, update the mastery levels for relevant learning objectives.

Mastery Levels:
- not_started: Learner hasn't encountered this topic yet
- learning: Learner is being introduced to the concept, asking questions
- practiced: Learner has applied the concept correctly at least once
- mastered: Learner demonstrates consistent understanding and application

Recent Conversation:
{conversation_text}

Current Learning Objectives:
{objectives_text}

Analyze the conversation and determine which objectives show progress. Return ONLY valid JSON (no markdown):
{{
  "updates": [
    {{
      "id": 1,
      "mastery_level": "learning",
      "reason": "Learner asked clarifying questions about this concept"
    }}
  ]
}}

Only include objectives that show clear evidence of progress. Return empty array if no progress detected."""

    try:
        response = client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,  # Low temperature for consistency
            max_tokens=1500
        )

        response_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
            if response_text.startswith("json"):
                response_text = "\n".join(response_text.split("\n")[1:])

        # Parse JSON
        assessment = json.loads(response_text)
        updates = assessment.get("updates", [])

        logger.info(f"LLM recommended {len(updates)} mastery updates")

        # Apply updates to objective tree
        for update in updates:
            obj_id = update.get("id")
            mastery_level = update.get("mastery_level")
            reason = update.get("reason", "")

            if update_mastery_by_id(objective_tree, obj_id, mastery_level):
                logger.info(f"Updated objective {obj_id} to {mastery_level}: {reason}")

        # Save updated tree
        if updates:
            objectives = load_learning_objectives()
            objectives["active_objective"] = objective_tree
            save_learning_objectives(objectives)

        return updates

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mastery assessment JSON: {e}")
        logger.error(f"Response text: {response_text}")
        return []

    except Exception as e:
        logger.error(f"Error in mastery assessment: {e}")
        return []


def format_objectives_for_prompt(obj_tree: dict, depth: int = 0) -> str:
    """
    Format objectives tree as text for LLM prompt.

    Args:
        obj_tree: Objective tree
        depth: Current depth (for indentation)

    Returns:
        str: Formatted objectives text
    """
    if not obj_tree:
        return "No active objectives"

    indent = "  " * depth
    text = f"{indent}[ID: {obj_tree['id']}] {obj_tree['title']} (mastery: {obj_tree['mastery_level']})\n"
    text += f"{indent}  Description: {obj_tree['description']}\n"

    for child in obj_tree.get("children", []):
        text += format_objectives_for_prompt(child, depth + 1)

    return text


def build_objectives_context() -> str:
    """
    Build context string from learning objectives for system prompt.

    Returns:
        str: Formatted context string with learning objectives, or empty string if none
    """
    active_objective = get_active_objective()

    if not active_objective:
        return ""

    context = "=" * 80 + "\n"
    context += "CURRENT LEARNING OBJECTIVES\n"
    context += "=" * 80 + "\n\n"
    context += "The learner has an active learning path. Here is their current objective hierarchy:\n\n"
    context += format_objectives_for_prompt(active_objective)
    context += "\n"
    context += "When the learner asks about their learning objectives or progress, refer to this hierarchy.\n"
    context += "Track their mastery levels and provide guidance based on their current progress.\n"
    context += "=" * 80 + "\n"

    return context


# ============================================================================
# Validation
# ============================================================================

def validate_objective_structure(objective: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate objective structure.

    Args:
        objective: Objective to validate

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    required_fields = ["id", "title", "description", "mastery_level", "children"]

    for field in required_fields:
        if field not in objective:
            return False, f"Missing required field: {field}"

    if objective["mastery_level"] not in MASTERY_LEVELS:
        return False, f"Invalid mastery level: {objective['mastery_level']}"

    if not isinstance(objective["children"], list):
        return False, "Children must be a list"

    # Recursively validate children
    for child in objective["children"]:
        is_valid, error = validate_objective_structure(child)
        if not is_valid:
            return False, error

    return True, None
