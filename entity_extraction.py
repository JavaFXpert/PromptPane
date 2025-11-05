"""
Entity Extraction Module

Uses LLM to extract structured entities from conversation messages
for building a knowledge graph.
"""

import json
from typing import Optional
from groq import Groq
import config
from error_handling import logger

# System prompt for entity extraction
ENTITY_EXTRACTION_PROMPT = """You are an expert at extracting structured information from conversations.

Your task is to identify and extract factual entities from the conversation that should be remembered for future reference.

Entity Types:
- person: Names of people mentioned (value should be their relationship or role)
- date: Important dates, birthdays, anniversaries (value should be the date)
- fact: General facts about the user (value should be the fact)
- preference: User preferences, likes, dislikes (value should be the preference)
- location: Places, addresses, cities (value should be the location details)
- relationship: Relationships between people (extract as separate entities)

Guidelines:
1. Only extract FACTUAL information that's clearly stated, not opinions or temporary things
2. Focus on information that would be useful to remember in future conversations
3. For people, the value should describe their relationship to the user (e.g., "brother", "colleague", "friend")
4. For dates, standardize to YYYY-MM-DD if full date is given, or "MM-DD" for recurring dates like birthdays
5. Be conservative - only extract high-confidence entities
6. The name field should be concise (e.g., "John", "Mom's birthday", "favorite food")
7. Use the description field for additional context if needed

Return ONLY a valid JSON array of entities. Each entity must have:
{
  "entity_type": "person|date|fact|preference|location",
  "name": "concise name",
  "value": "the value or relationship",
  "description": "optional additional context",
  "confidence": 0.0-1.0
}

If no entities are found, return an empty array: []

Examples:

User: "My brother John lives in Seattle and works as a software engineer"
Assistant: [
  {"entity_type": "person", "name": "John", "value": "brother", "description": "lives in Seattle, software engineer", "confidence": 0.95},
  {"entity_type": "location", "name": "John's location", "value": "Seattle", "description": "where John lives", "confidence": 0.9}
]

User: "I prefer tea over coffee"
Assistant: [
  {"entity_type": "preference", "name": "beverage preference", "value": "tea over coffee", "description": "", "confidence": 0.9}
]

User: "My mom's birthday is June 15th"
Assistant: [
  {"entity_type": "person", "name": "Mom", "value": "mother", "description": "", "confidence": 1.0},
  {"entity_type": "date", "name": "Mom's birthday", "value": "06-15", "description": "recurring annual date", "confidence": 0.95}
]

User: "What's the weather like?"
Assistant: []

Now extract entities from this conversation:"""


def extract_entities_from_conversation(
    user_message: str,
    assistant_response: str,
    client: Groq,
    model: str = None,
    temperature: float = 0.3
) -> list[dict]:
    """
    Extract entities from a user message and assistant response pair.

    Args:
        user_message: The user's message
        assistant_response: The assistant's response
        client: Groq API client
        model: Model to use (defaults to config.GROQ_MODEL)
        temperature: Temperature for extraction (lower = more conservative)

    Returns:
        List of extracted entity dictionaries
    """
    if model is None:
        model = config.GROQ_MODEL

    # Build the conversation context for extraction
    conversation_text = f"User: {user_message}\nAssistant: {assistant_response}"

    try:
        # Call LLM for entity extraction
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": ENTITY_EXTRACTION_PROMPT},
                {"role": "user", "content": conversation_text}
            ],
            model=model,
            temperature=temperature,
            max_tokens=1000
        )

        # Parse the response
        content = response.choices[0].message.content.strip()

        # Extract JSON from response (handle potential markdown code blocks)
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Parse JSON
        entities = json.loads(content)

        # Validate structure
        if not isinstance(entities, list):
            logger.warning(f"Entity extraction returned non-list: {content}")
            return []

        # Validate each entity has required fields
        validated_entities = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue

            # Check required fields
            if not all(k in entity for k in ["entity_type", "name", "value", "confidence"]):
                logger.warning(f"Skipping malformed entity: {entity}")
                continue

            # Ensure description exists
            if "description" not in entity:
                entity["description"] = ""

            # Validate confidence
            if not isinstance(entity["confidence"], (int, float)):
                entity["confidence"] = 0.5
            entity["confidence"] = max(0.0, min(1.0, float(entity["confidence"])))

            # Validate entity type
            valid_types = ["person", "date", "fact", "preference", "location", "relationship"]
            if entity["entity_type"] not in valid_types:
                logger.warning(f"Invalid entity type: {entity['entity_type']}")
                continue

            validated_entities.append(entity)

        logger.info(f"Extracted {len(validated_entities)} entities from conversation")
        return validated_entities

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse entity extraction JSON: {e}")
        logger.debug(f"Response content: {content}")
        return []
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}", exc_info=True)
        return []


def should_extract_entities(user_message: str, assistant_response: str) -> bool:
    """
    Determine if we should attempt entity extraction for this conversation.

    Skips extraction for very short messages or common queries that won't
    contain factual information worth remembering.

    Args:
        user_message: The user's message
        assistant_response: The assistant's response

    Returns:
        True if extraction should be attempted
    """
    # Skip very short messages
    if len(user_message) < 10:
        return False

    # Skip common non-factual queries
    common_queries = [
        "what", "how", "why", "when", "where", "who",
        "explain", "tell me about", "help", "can you"
    ]

    message_lower = user_message.lower()

    # If message is a pure question without sharing information, skip
    is_pure_question = any(message_lower.startswith(q) for q in common_queries)
    has_personal_info = any(word in message_lower for word in ["my", "i ", "i'm", "i've", "me"])

    if is_pure_question and not has_personal_info:
        return False

    # Skip if assistant response indicates no factual information shared
    skip_responses = [
        "i don't know",
        "i cannot",
        "i can't",
        "rate limit",
        "error",
        "sorry"
    ]

    response_lower = assistant_response.lower()
    if any(phrase in response_lower for phrase in skip_responses):
        return False

    return True
