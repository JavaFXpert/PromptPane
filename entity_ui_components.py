"""
Entity UI Components

UI components for entity management sidebar and related functionality.
Displays the global knowledge graph with grouping, editing, and deletion.
"""

from fasthtml.common import *
from monsterui.all import *
from datetime import datetime
from typing import Any

# Entity type to display label mapping
ENTITY_TYPE_LABELS = {
    "person": "👥 People",
    "date": "📅 Important Dates",
    "fact": "💡 Facts",
    "preference": "⭐ Preferences",
    "location": "📍 Locations",
    "relationship": "🔗 Relationships"
}

# Entity type to emoji mapping (for individual items)
ENTITY_TYPE_ICONS = {
    "person": "👤",
    "date": "📅",
    "fact": "💡",
    "preference": "⭐",
    "location": "📍",
    "relationship": "🔗"
}


def EntityListItem(entity: dict, show_actions: bool = True) -> Any:
    """
    Render a single entity item.

    Args:
        entity: Entity dictionary with id, name, value, type, etc.
        show_actions: Whether to show edit/delete buttons

    Returns:
        Entity list item component
    """
    entity_id = entity["id"]
    entity_type = entity["entity_type"]
    name = entity["name"]
    value = entity["value"]
    description = entity.get("description", "")
    confidence = entity.get("confidence", 1.0)
    mention_count = entity.get("mention_count", 1)

    # Get icon for entity type
    icon = ENTITY_TYPE_ICONS.get(entity_type, "•")

    # Build display text with key type-specific attributes
    detail_parts = [value]

    # Add key type-specific attributes to display
    if entity_type == "person":
        if entity.get("birthdate"):
            detail_parts.append(f"Born: {entity['birthdate']}")
        if entity.get("gender"):
            detail_parts.append(entity['gender'].capitalize())
    elif entity_type == "date":
        if entity.get("recurring"):
            detail_parts.append("Recurring")
        if entity.get("importance"):
            detail_parts.append(f"{entity['importance'].capitalize()} priority")
    elif entity_type == "preference":
        if entity.get("strength"):
            detail_parts.append(f"{entity['strength'].capitalize()} preference")

    if description:
        detail_parts.append(description)

    detail_text = " • ".join(detail_parts)

    return Div(
        # Left side: icon and entity info
        Div(
            # Icon
            Span(icon, cls="text-xl mr-2"),

            # Entity info
            Div(
                # Entity name
                Div(
                    name,
                    cls="font-medium text-sm",
                    id=f"entity-name-{entity_id}"
                ),

                # Value and description
                Div(
                    detail_text,
                    cls="text-xs text-muted-foreground"
                ),

                # Metadata
                Div(
                    f"Mentioned {mention_count}× • {int(confidence * 100)}% confidence",
                    cls="text-xs text-muted-foreground opacity-70"
                ),

                cls="flex-1 min-w-0"
            ),

            cls="flex items-start flex-1 min-w-0"
        ),

        # Right side: actions (show on hover)
        Div(
            # Edit button
            Button(
                "✏️",
                cls="btn btn-ghost btn-xs",
                hx_get=f"/entity/{entity_id}/edit-form",
                hx_target=f"#entity-{entity_id}",
                hx_swap="outerHTML",
                title="Edit entity"
            ) if show_actions else None,

            # Delete button
            Button(
                "🗑️",
                cls="btn btn-ghost btn-xs",
                hx_delete=f"/entity/{entity_id}/delete",
                hx_confirm=f"Delete '{name}'? This cannot be undone.",
                hx_target=f"#entity-{entity_id}",
                hx_swap="outerHTML swap:0.3s",
                title="Delete entity"
            ) if show_actions else None,

            cls="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
        ) if show_actions else None,

        id=f"entity-{entity_id}",
        cls="flex items-start justify-between p-2 rounded hover:bg-base-200 transition-all group"
    )


def EntityEditForm(entity: dict) -> Any:
    """
    Inline form for editing an entity.

    Args:
        entity: Entity dictionary to edit

    Returns:
        Edit form component
    """
    entity_id = entity["id"]
    entity_type = entity.get("entity_type", "")

    # Core fields that are always present and shown
    core_fields = {"id", "entity_type", "name", "value", "description", "confidence",
                   "created_at", "last_mentioned", "mention_count"}

    # Get type-specific attributes (anything not in core fields)
    type_specific_attrs = {k: v for k, v in entity.items() if k not in core_fields}

    # Build form fields
    form_fields = []

    # Core fields
    form_fields.extend([
        # Name field
        Div(
            Label("Name", cls="label label-text text-xs"),
            Input(
                type="text",
                name="name",
                value=entity["name"],
                cls="input input-bordered input-xs w-full",
                required=True
            ),
            cls="form-control mb-2"
        ),

        # Value field
        Div(
            Label("Value", cls="label label-text text-xs"),
            Input(
                type="text",
                name="value",
                value=entity["value"],
                cls="input input-bordered input-xs w-full",
                required=True
            ),
            cls="form-control mb-2"
        ),

        # Description field
        Div(
            Label("Description (optional)", cls="label label-text text-xs"),
            Input(
                type="text",
                name="description",
                value=entity.get("description", ""),
                cls="input input-bordered input-xs w-full"
            ),
            cls="form-control mb-2"
        ),
    ])

    # Type-specific attributes section
    if type_specific_attrs:
        form_fields.append(
            Div(
                Label("Type-Specific Attributes", cls="label label-text text-xs font-bold mt-2"),
                cls="form-control mb-1"
            )
        )

        for attr_name, attr_value in sorted(type_specific_attrs.items()):
            field = _create_type_specific_field(attr_name, attr_value, entity_type)
            if field:
                form_fields.append(field)

    # Confidence field
    form_fields.append(
        Div(
            Label(f"Confidence: {int(entity.get('confidence', 1.0) * 100)}%", cls="label label-text text-xs"),
            Input(
                type="range",
                name="confidence",
                value=str(entity.get("confidence", 1.0)),
                min="0",
                max="1",
                step="0.1",
                cls="range range-xs",
                oninput="this.previousElementSibling.textContent = `Confidence: ${Math.round(this.value * 100)}%`"
            ),
            cls="form-control mb-3"
        )
    )

    # Buttons
    form_fields.append(
        Div(
            Button("✓", type="submit", cls="btn btn-success btn-xs"),
            Button(
                "✕",
                type="button",
                cls="btn btn-ghost btn-xs",
                hx_get=f"/entity/{entity_id}/cancel-edit",
                hx_target=f"#entity-{entity_id}",
                hx_swap="outerHTML"
            ),
            cls="flex gap-1"
        )
    )

    return Form(
        Div(
            *form_fields,
            cls="space-y-2"
        ),

        hx_put=f"/entity/{entity_id}/update",
        hx_target=f"#entity-{entity_id}",
        hx_swap="outerHTML",
        cls="p-2 bg-base-200 rounded",
        id=f"entity-{entity_id}"
    )


def _create_type_specific_field(attr_name: str, attr_value: Any, entity_type: str) -> Any:
    """
    Create an appropriate input field for a type-specific attribute.

    Args:
        attr_name: Name of the attribute
        attr_value: Current value of the attribute
        entity_type: Type of entity (person, date, etc.)

    Returns:
        Form control component for this attribute
    """
    # Handle boolean fields
    if isinstance(attr_value, bool):
        return Div(
            Label(
                Input(
                    type="checkbox",
                    name=f"attr_{attr_name}",
                    value="true",
                    checked=attr_value,
                    cls="checkbox checkbox-xs mr-2"
                ),
                attr_name.replace("_", " ").capitalize(),
                cls="label label-text text-xs cursor-pointer"
            ),
            cls="form-control mb-2"
        )

    # Handle select fields for known attributes
    if attr_name == "importance":
        return Div(
            Label(attr_name.replace("_", " ").capitalize(), cls="label label-text text-xs"),
            Select(
                Option("low", value="low", selected=(attr_value == "low")),
                Option("medium", value="medium", selected=(attr_value == "medium")),
                Option("high", value="high", selected=(attr_value == "high")),
                name=f"attr_{attr_name}",
                cls="select select-bordered select-xs w-full"
            ),
            cls="form-control mb-2"
        )

    if attr_name == "strength":
        return Div(
            Label(attr_name.replace("_", " ").capitalize(), cls="label label-text text-xs"),
            Select(
                Option("weak", value="weak", selected=(attr_value == "weak")),
                Option("moderate", value="moderate", selected=(attr_value == "moderate")),
                Option("strong", value="strong", selected=(attr_value == "strong")),
                name=f"attr_{attr_name}",
                cls="select select-bordered select-xs w-full"
            ),
            cls="form-control mb-2"
        )

    if attr_name == "gender":
        return Div(
            Label(attr_name.replace("_", " ").capitalize(), cls="label label-text text-xs"),
            Select(
                Option("", value="", selected=(not attr_value)),
                Option("male", value="male", selected=(attr_value == "male")),
                Option("female", value="female", selected=(attr_value == "female")),
                Option("other", value="other", selected=(attr_value not in ["male", "female", ""])),
                name=f"attr_{attr_name}",
                cls="select select-bordered select-xs w-full"
            ),
            cls="form-control mb-2"
        )

    # Handle date fields
    if attr_name == "birthdate" or "date" in attr_name.lower():
        return Div(
            Label(attr_name.replace("_", " ").capitalize(), cls="label label-text text-xs"),
            Input(
                type="date",
                name=f"attr_{attr_name}",
                value=str(attr_value) if attr_value else "",
                cls="input input-bordered input-xs w-full"
            ),
            cls="form-control mb-2"
        )

    # Handle number fields
    if isinstance(attr_value, (int, float)) and not isinstance(attr_value, bool):
        return Div(
            Label(attr_name.replace("_", " ").capitalize(), cls="label label-text text-xs"),
            Input(
                type="number",
                name=f"attr_{attr_name}",
                value=str(attr_value),
                cls="input input-bordered input-xs w-full"
            ),
            cls="form-control mb-2"
        )

    # Handle list/array fields
    if isinstance(attr_value, list):
        value_str = ", ".join(str(v) for v in attr_value)
        return Div(
            Label(f"{attr_name.replace('_', ' ').capitalize()} (comma-separated)", cls="label label-text text-xs"),
            Input(
                type="text",
                name=f"attr_{attr_name}",
                value=value_str,
                cls="input input-bordered input-xs w-full",
                placeholder="item1, item2, item3"
            ),
            cls="form-control mb-2"
        )

    # Default: text field for strings and other types
    return Div(
        Label(attr_name.replace("_", " ").capitalize(), cls="label label-text text-xs"),
        Input(
            type="text",
            name=f"attr_{attr_name}",
            value=str(attr_value) if attr_value is not None else "",
            cls="input input-bordered input-xs w-full"
        ),
        cls="form-control mb-2"
    )


def EntityTypeGroup(entity_type: str, entities: list[dict]) -> Any:
    """
    Render a group of entities of the same type.

    Args:
        entity_type: The entity type (person, date, fact, etc.)
        entities: List of entities of this type

    Returns:
        Entity type group component
    """
    label = ENTITY_TYPE_LABELS.get(entity_type, entity_type.capitalize())

    return Div(
        # Group header
        Div(
            H4(label, cls="font-semibold text-sm"),
            Span(
                f"{len(entities)}",
                cls="badge badge-sm badge-primary"
            ),
            cls="flex items-center justify-between mb-2"
        ),

        # Entity list
        Div(
            *[EntityListItem(entity) for entity in entities],
            cls="space-y-1"
        ),

        cls="mb-4"
    )


def EntitySidebar(entities: list[dict], search_query: str = "") -> Any:
    """
    Render the entity management sidebar.

    Args:
        entities: List of all entities
        search_query: Current search query (if any)

    Returns:
        Entity sidebar component
    """
    # Filter entities by search query
    if search_query:
        search_lower = search_query.lower()
        entities = [
            e for e in entities
            if search_lower in e["name"].lower()
            or search_lower in e["value"].lower()
            or search_lower in e.get("description", "").lower()
        ]

    # Group entities by type
    by_type = {}
    for entity in entities:
        entity_type = entity["entity_type"]
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append(entity)

    # Sort each type by mention count and name
    for entity_type in by_type:
        by_type[entity_type].sort(
            key=lambda e: (-e.get("mention_count", 0), e["name"])
        )

    # Build type groups in order
    type_order = ["person", "date", "preference", "fact", "location", "relationship"]
    type_groups = []
    for entity_type in type_order:
        if entity_type in by_type:
            type_groups.append(EntityTypeGroup(entity_type, by_type[entity_type]))

    # Add any other types not in the standard order
    for entity_type in by_type:
        if entity_type not in type_order:
            type_groups.append(EntityTypeGroup(entity_type, by_type[entity_type]))

    return Div(
        # Header
        Div(
            H2("🧠 Knowledge Graph", cls="text-lg font-bold"),
            Div(
                Span(
                    f"{len(entities)} entities",
                    cls="text-xs text-muted-foreground"
                ),
                cls="flex items-center gap-2"
            ),
            cls="flex items-center justify-between mb-3 p-3 border-b border-base-300"
        ),

        # Search box
        Form(
            Input(
                type="text",
                name="q",
                placeholder="Search entities...",
                value=search_query,
                cls="input input-bordered input-sm w-full",
                hx_get="/entities/search",
                hx_target="#entity-content",
                hx_swap="innerHTML",
                hx_trigger="keyup changed delay:300ms"
            ),
            cls="px-3 mb-3"
        ),

        # Entity list
        Div(
            *type_groups if type_groups else [
                Div(
                    Div(
                        "🔍",
                        cls="text-4xl mb-2"
                    ),
                    P(
                        "No entities found" if search_query else "No entities yet",
                        cls="text-sm text-muted-foreground"
                    ),
                    cls="flex flex-col items-center justify-center p-8 text-center"
                )
            ],
            id="entity-content",
            cls="px-3 overflow-y-auto",
            style="max-height: calc(100vh - 180px);"
        ),

        cls="w-80 bg-base-100 border-l border-base-300 flex flex-col",
        id="entity-sidebar"
    )


def EmptyEntityState() -> Any:
    """
    Render empty state when no entities exist.

    Returns:
        Empty state component
    """
    return Div(
        Div(
            "🧠",
            cls="text-6xl mb-4"
        ),
        H3("No Knowledge Yet", cls="text-lg font-semibold mb-2"),
        P(
            "Start chatting to build your knowledge graph!",
            cls="text-sm text-muted-foreground mb-4"
        ),
        P(
            "The AI will automatically extract and remember facts, people, dates, and preferences from your conversations.",
            cls="text-xs text-muted-foreground max-w-xs text-center"
        ),
        cls="flex flex-col items-center justify-center p-8 text-center h-full"
    )
