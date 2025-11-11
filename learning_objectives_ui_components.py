"""
Learning Objectives UI Components

UI components for displaying and interacting with hierarchical learning objectives.
Includes tree view, mastery badges, and confirmation modals.
"""

from fasthtml.common import *
from monsterui.all import *


# ============================================================================
# Mastery Level Configuration
# ============================================================================

MASTERY_CONFIG = {
    "not_started": {
        "label": "Not Started",
        "color": "badge-ghost",
        "icon": "○",
        "description": "Not yet encountered"
    },
    "learning": {
        "label": "Learning",
        "color": "badge-info",
        "icon": "◐",
        "description": "Being introduced to concept"
    },
    "practiced": {
        "label": "Practiced",
        "color": "badge-warning",
        "icon": "◑",
        "description": "Applied at least once"
    },
    "mastered": {
        "label": "Mastered",
        "color": "badge-success",
        "icon": "●",
        "description": "Consistent understanding"
    }
}


def get_mastery_badge(mastery_level: str) -> Any:
    """
    Create a badge component for a mastery level.

    Args:
        mastery_level: Mastery level (not_started, learning, practiced, mastered)

    Returns:
        Badge component
    """
    config = MASTERY_CONFIG.get(mastery_level, MASTERY_CONFIG["not_started"])

    return Span(
        config["icon"] + " " + config["label"],
        cls=f"badge {config['color']} badge-sm",
        title=config["description"]
    )


def get_progress_percentage(objective: dict) -> int:
    """
    Calculate progress percentage based on children's mastery.

    Args:
        objective: Objective with children

    Returns:
        int: Progress percentage (0-100)
    """
    children = objective.get("children", [])

    if not children:
        # Leaf node: 100% if mastered, 0% otherwise
        return 100 if objective.get("mastery_level") == "mastered" else 0

    # Calculate based on children
    total = len(children)
    mastered = sum(1 for child in children if child.get("mastery_level") == "mastered")

    return int((mastered / total) * 100) if total > 0 else 0


# ============================================================================
# Tree View Components
# ============================================================================

def ObjectiveTreeItem(objective: dict, depth: int = 0, expanded: bool = True) -> Any:
    """
    Recursive tree item for displaying a learning objective with children.

    Args:
        objective: Objective to display
        depth: Current depth in tree (for indentation)
        expanded: Whether children are initially expanded

    Returns:
        Div with objective and children
    """
    obj_id = objective.get("id", 0)
    title = objective.get("title", "Untitled")
    description = objective.get("description", "")
    mastery_level = objective.get("mastery_level", "not_started")
    children = objective.get("children", [])
    has_children = len(children) > 0

    # Calculate progress
    progress = get_progress_percentage(objective)

    # Indentation based on depth
    indent_class = f"ml-{depth * 4}" if depth > 0 else ""

    # Expand/collapse icon
    if has_children:
        expand_icon = "▼" if expanded else "▶"
        expand_cursor = "cursor-pointer"
    else:
        expand_icon = "•"
        expand_cursor = ""

    return Div(
        # Objective header (clickable to expand/collapse)
        Div(
            # Expand/collapse icon
            Span(
                expand_icon,
                cls=f"text-base-content {expand_cursor} select-none w-4",
                id=f"icon-{obj_id}",
                onclick=f"toggleObjective({obj_id})" if has_children else None,
            ),
            # Objective content
            Div(
                # Title and mastery badge
                Div(
                    Span(title, cls="font-medium text-sm"),
                    get_mastery_badge(mastery_level),
                    cls="flex items-center gap-2 mb-1"
                ),
                # Description
                P(description, cls="text-xs text-base-content opacity-70 mb-1"),
                # Progress bar (if has children)
                (
                    Div(
                        Div(
                            cls=f"h-1 bg-success rounded",
                            style=f"width: {progress}%"
                        ),
                        cls="w-full bg-base-300 rounded h-1 mb-1"
                    ) if has_children else None
                ),
                cls="flex-1"
            ),
            cls="flex items-start gap-2 p-2 hover:bg-base-200 rounded transition-colors"
        ),
        # Children container (initially expanded or collapsed)
        Div(
            *[ObjectiveTreeItem(child, depth + 1, expanded=False) for child in children],
            id=f"children-{obj_id}",
            cls="" if (expanded and has_children) else "hidden",
            style="display: " + ("block" if expanded else "none") if has_children else "display: none"
        ),
        cls=indent_class,
        id=f"objective-{obj_id}"
    )


def NoActiveObjectiveState() -> Any:
    """
    Empty state when no active learning objective exists.

    Returns:
        Div with empty state message
    """
    return Div(
        Div(
            # Icon
            Div(
                "🎯",
                cls="text-6xl mb-4"
            ),
            # Message
            H3("No Active Learning Path", cls="text-lg font-bold mb-2"),
            P(
                "Start a learning journey by telling me what you'd like to learn!",
                cls="text-sm text-base-content opacity-70 mb-4 text-center"
            ),
            # Example prompts
            Div(
                P("Try saying:", cls="text-xs font-semibold mb-2"),
                Ul(
                    Li('"I want to learn Python"', cls="text-xs mb-1"),
                    Li('"Teach me calculus"', cls="text-xs mb-1"),
                    Li('"Help me understand quantum physics"', cls="text-xs"),
                    cls="text-base-content opacity-60"
                ),
                cls="text-left"
            ),
            cls="flex flex-col items-center justify-center h-full p-6"
        ),
        cls="w-full h-full flex items-center justify-center"
    )


# ============================================================================
# Sidebar Component
# ============================================================================

def ObjectiveSidebar(objective_tree: dict = None) -> Any:
    """
    Sidebar component for displaying learning objectives tree.

    Args:
        objective_tree: Active objective tree (None if no active objective)

    Returns:
        Div with sidebar content
    """
    has_objective = objective_tree is not None

    return Div(
        # Header
        Div(
            H2("Learning Path", cls="text-lg font-bold"),
            # Clear button (only if has active objective)
            (
                Button(
                    "×",
                    cls="btn btn-ghost btn-xs btn-circle",
                    hx_delete="/objective/clear",
                    hx_target="#objectives-sidebar-content",
                    hx_swap="innerHTML",
                    hx_confirm="Clear this learning path? It will be archived.",
                    title="Clear learning path"
                ) if has_objective else None
            ),
            cls="flex items-center justify-between p-4 border-b border-base-300"
        ),
        # Content area
        Div(
            # Show tree or empty state
            (
                Div(
                    ObjectiveTreeItem(objective_tree, depth=0, expanded=True),
                    cls="p-4"
                ) if has_objective else NoActiveObjectiveState()
            ),
            id="objectives-sidebar-content",
            cls="overflow-y-auto",
            style="max-height: calc(100vh - 80px);"
        ),
        # JavaScript for expand/collapse
        Script("""
function toggleObjective(objId) {
    const icon = document.getElementById('icon-' + objId);
    const children = document.getElementById('children-' + objId);

    if (children && children.children.length > 0) {
        const isHidden = children.style.display === 'none';
        children.style.display = isHidden ? 'block' : 'none';
        icon.textContent = isHidden ? '▼' : '▶';
    }
}
        """),
        cls="flex flex-col h-full",
        id="objectives-sidebar"
    )


# ============================================================================
# Confirmation Modal
# ============================================================================

def ReplaceObjectiveConfirmationModal(
    new_topic: str,
    existing_title: str
) -> Any:
    """
    Modal to confirm replacing existing learning objective.

    Args:
        new_topic: New topic the user wants to learn
        existing_title: Title of existing active objective

    Returns:
        Modal component
    """
    return Div(
        # Modal backdrop
        Div(
            cls="modal-backdrop",
            onclick="document.getElementById('replace-modal').close()"
        ),
        # Modal dialog
        Dialog(
            Div(
                # Header
                H3("Replace Learning Path?", cls="font-bold text-lg mb-4"),
                # Message
                Div(
                    P(
                        f"You're currently learning: ",
                        Strong(existing_title),
                        cls="mb-2"
                    ),
                    P(
                        f"Starting a new path (",
                        Strong(new_topic),
                        ") will archive your current progress.",
                        cls="mb-4"
                    ),
                    P(
                        "Your progress will be saved in history and you can return to it later.",
                        cls="text-sm text-base-content opacity-70"
                    ),
                    cls="py-4"
                ),
                # Actions
                Div(
                    Button(
                        "Cancel",
                        cls="btn btn-ghost",
                        onclick="document.getElementById('replace-modal').close()"
                    ),
                    Button(
                        "Replace & Start New Path",
                        cls="btn btn-primary",
                        hx_post="/objective/create-from-chat",
                        hx_vals=f'{{"topic": "{new_topic}", "replace": true}}',
                        hx_target="#objectives-sidebar-content",
                        hx_swap="innerHTML",
                        onclick="document.getElementById('replace-modal').close()"
                    ),
                    cls="flex gap-2 justify-end"
                ),
                cls="modal-box"
            ),
            id="replace-modal",
            cls="modal"
        ),
        id="replace-modal-container"
    )


# ============================================================================
# Compact Summary Component (for chat interface)
# ============================================================================

def ObjectiveSummaryCard(objective_tree: dict) -> Any:
    """
    Compact summary card of learning objectives for display in chat.

    Args:
        objective_tree: Active objective tree

    Returns:
        Card component with summary
    """
    if not objective_tree:
        return Div()

    title = objective_tree.get("title", "Untitled")
    children = objective_tree.get("children", [])
    total_count = count_all_objectives(objective_tree)
    mastered_count = count_mastered_objectives(objective_tree)
    progress = int((mastered_count / total_count) * 100) if total_count > 0 else 0

    return Div(
        Card(
            CardHeader(
                H3("📚 Learning Path Created", cls="text-md font-bold")
            ),
            CardBody(
                P(title, cls="font-semibold mb-2"),
                P(
                    f"Decomposed into {len(children)} main areas with {total_count} total objectives.",
                    cls="text-sm mb-3"
                ),
                # Progress bar
                Div(
                    Div(
                        cls=f"h-2 bg-success rounded",
                        style=f"width: {progress}%"
                    ),
                    cls="w-full bg-base-300 rounded h-2 mb-2"
                ),
                P(
                    f"{mastered_count} / {total_count} objectives mastered",
                    cls="text-xs text-base-content opacity-70"
                ),
                # View in sidebar link
                P(
                    "→ View full tree in the Learning Path sidebar",
                    cls="text-xs text-primary mt-2"
                )
            )
        ),
        cls="my-4"
    )


def count_all_objectives(objective: dict) -> int:
    """
    Count total number of objectives in tree.

    Args:
        objective: Root objective

    Returns:
        int: Total count
    """
    count = 1
    for child in objective.get("children", []):
        count += count_all_objectives(child)
    return count


def count_mastered_objectives(objective: dict) -> int:
    """
    Count number of mastered objectives in tree.

    Args:
        objective: Root objective

    Returns:
        int: Mastered count
    """
    count = 1 if objective.get("mastery_level") == "mastered" else 0
    for child in objective.get("children", []):
        count += count_mastered_objectives(child)
    return count
