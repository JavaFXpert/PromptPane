"""
Session UI Components

UI components for session management sidebar and related functionality.
"""

from fasthtml.common import *
from monsterui.all import *
from datetime import datetime
from typing import Any

def SessionListItem(session: dict, current_session_id: str) -> Any:
    """
    Render a single session item in the sidebar.

    Args:
        session: Session metadata dictionary
        current_session_id: ID of the currently active session

    Returns:
        Session list item component
    """
    is_current = session["session_id"] == current_session_id

    # Parse timestamp for display
    try:
        last_accessed = datetime.fromisoformat(session["last_accessed"])
        time_display = last_accessed.strftime("%b %d, %I:%M %p")
    except:
        time_display = "Recently"

    # Build CSS classes
    if is_current:
        item_cls = "flex items-center justify-between p-3 rounded-lg transition-all bg-primary text-primary-content"
    else:
        item_cls = "flex items-center justify-between p-3 rounded-lg transition-all hover:bg-base-200"

    return Div(
        # Left side: icon and info
        Div(
            # Icon
            Span(session["icon"], cls="text-2xl mr-3"),

            # Session info
            Div(
                # Session name (clickable to switch)
                Div(
                    session["name"],
                    cls="font-semibold text-sm cursor-pointer" if is_current else "font-medium text-sm cursor-pointer",
                    hx_get=f"/session/{session['session_id']}/switch",
                    hx_target="body",
                    hx_swap="outerHTML",
                    id=f"session-name-{session['session_id']}"
                ),

                # Message count and time
                Div(
                    f"{session['message_count']} messages • {time_display}",
                    cls="text-xs opacity-70"
                ),

                cls="flex-1"
            ),

            cls="flex items-center flex-1 min-w-0"
        ),

        # Right side: actions (show on hover)
        Div(
            # Rename button
            Button(
                "✏️",
                cls="btn btn-ghost btn-xs",
                hx_get=f"/session/{session['session_id']}/rename-form",
                hx_target=f"#session-name-{session['session_id']}",
                hx_swap="outerHTML",
                title="Rename session",
                onclick="event.stopPropagation();"
            ),

            # Delete button (not for current session)
            Button(
                "🗑️",
                cls="btn btn-ghost btn-xs",
                hx_delete=f"/session/{session['session_id']}/delete",
                hx_confirm=f"Delete '{session['name']}' and all its messages?",
                hx_target=f"#session-{session['session_id']}",
                hx_swap="outerHTML swap:0.3s",
                title="Delete session",
                onclick="event.stopPropagation();"
            ) if not is_current else None,

            cls="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
        ),

        id=f"session-{session['session_id']}",
        cls=f"{item_cls} group"
    )


def SessionRenameInlineForm(session: dict) -> Any:
    """
    Inline form for renaming a session (replaces session name).

    Args:
        session: Session metadata dictionary

    Returns:
        Inline rename form component
    """
    session_id = session['session_id']

    return Form(
        Input(
            type="text",
            name="name",
            value=session["name"],
            cls="input input-bordered input-xs w-full text-sm",
            autofocus=True,
            onclick="event.stopPropagation();",
            required=True
        ),
        Button("✓", type="submit", cls="btn btn-success btn-xs", onclick="event.stopPropagation();"),
        Button(
            "✕",
            type="button",
            cls="btn btn-ghost btn-xs",
            hx_get=f"/session/{session_id}/rename-cancel",
            hx_target=f"#session-name-{session_id}",
            hx_swap="outerHTML",
            onclick="event.stopPropagation();"
        ),

        hx_put=f"/session/{session_id}/rename",
        hx_target=f"#session-{session_id}",
        hx_swap="outerHTML",
        onsubmit="event.stopPropagation();",
        cls="flex gap-1 items-center",
        id=f"session-name-{session_id}"
    )


def SessionSidebar(sessions: list[dict], current_session_id: str) -> Any:
    """
    Render the session management sidebar.

    Args:
        sessions: List of session metadata dictionaries
        current_session_id: ID of the currently active session

    Returns:
        Session sidebar component
    """
    return Div(
        # Header
        Div(
            H2("Sessions", cls="text-lg font-bold"),

            # New session button
            Button(
                "+ New",
                cls="btn btn-primary btn-sm",
                hx_post="/session/new",
                hx_target="body",
                hx_swap="outerHTML"
            ),

            cls="flex items-center justify-between mb-4 p-4 border-b border-base-300"
        ),

        # Session list
        Div(
            *[SessionListItem(session, current_session_id) for session in sessions],

            id="session-list",
            cls="flex flex-col gap-2 p-4 overflow-y-auto",
            style="max-height: calc(100vh - 200px);"
        ),

        cls="w-80 bg-base-100 border-r border-base-300 flex flex-col",
        id="session-sidebar"
    )


def NewSessionModal(session_id: str) -> Any:
    """
    Modal for naming a new session.

    Args:
        session_id: The newly created session ID

    Returns:
        Modal component for session naming
    """
    return Div(
        Div(
            # Modal header
            H3("Name Your Session", cls="font-bold text-lg mb-4"),

            # Form
            Form(
                # Session name input
                Div(
                    Label("Session Name", cls="label"),
                    Input(
                        type="text",
                        name="name",
                        placeholder="e.g., Work Projects, Learning, Personal",
                        value=f"New Session",
                        cls="input input-bordered w-full",
                        autofocus=True
                    ),
                    cls="form-control mb-4"
                ),

                # Icon picker
                Div(
                    Label("Icon", cls="label"),
                    Div(
                        *[
                            Button(
                                icon,
                                type="button",
                                cls="btn btn-ghost btn-sm",
                                onclick=f"document.querySelector('input[name=icon]').value='{icon}'; this.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('btn-active')); this.classList.add('btn-active');"
                            )
                            for icon in ["💬", "💼", "📚", "🏠", "🎮", "🎨", "🔬", "✈️"]
                        ],
                        cls="flex gap-2 flex-wrap"
                    ),
                    Input(type="hidden", name="icon", value="💬"),
                    cls="form-control mb-4"
                ),

                # Buttons
                Div(
                    Button("Cancel", type="button", cls="btn", onclick="this.closest('.modal').remove()"),
                    Button("Create", type="submit", cls="btn btn-primary"),
                    cls="flex gap-2 justify-end"
                ),

                hx_post=f"/session/{session_id}/finalize",
                hx_target="body",
                hx_swap="outerHTML"
            ),

            cls="modal-box"
        ),

        cls="modal modal-open",
        onclick="if(event.target === this) this.remove()"
    )


def SessionRenameForm(session: dict) -> Any:
    """
    Inline form for renaming a session.

    Args:
        session: Session metadata dictionary

    Returns:
        Rename form component
    """
    return Form(
        Div(
            Input(
                type="text",
                name="name",
                value=session["name"],
                cls="input input-bordered input-sm w-full",
                autofocus=True
            ),

            Div(
                Button("✓", type="submit", cls="btn btn-success btn-xs"),
                Button("✕", type="button", cls="btn btn-ghost btn-xs",
                      onclick="this.closest('form').previousElementSibling.classList.remove('hidden'); this.closest('form').remove()"),
                cls="flex gap-1"
            ),

            cls="flex gap-2 items-center"
        ),

        hx_put=f"/session/{session['session_id']}/rename",
        hx_target=f"#session-{session['session_id']}",
        hx_swap="outerHTML"
    )
