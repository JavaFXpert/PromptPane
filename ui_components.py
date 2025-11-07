"""
PromptPane UI Components

This module contains UI rendering functions including:
- EmptyState: Empty chat display
- ChatMessage: Individual message bubble rendering
- ChatInterface: Main chat interface with form and interactions
"""

from fasthtml.common import *
from monsterui.all import *
from datetime import datetime
from typing import Optional, Callable, Any

# Import MUI components and processing
from mui_components import process_mui_tags, extract_concept_tags, restore_concepts

# Import utility functions
from utils import (
    extract_latex,
    restore_latex
)

# ============================================================================
# UI Component Rendering Functions
# ============================================================================

def EmptyState() -> Any:
    """Render the empty state message shown when there are no messages"""
    return Div(
        Div(
            DivCentered(
                UkIcon("message-circle", height=48, width=48, cls=TextT.muted),
                cls="mb-4"
            ),
            H4("No messages yet", cls=TextT.center + " mb-2"),
            P("Start a conversation by typing a message below.",
              cls=(TextT.muted, TextT.center)),
            cls="space-y-3 text-center"
        ),
        cls="flex items-center justify-center h-full"
    )

def ChatMessage(role: str, content: str, timestamp: Optional[datetime | str] = None, session_id: str = "default") -> Any:
    """Render a chat message bubble"""
    is_user: bool = role == "user"

    avatar = DiceBearAvatar(
        "User" if is_user else "Assistant",
        h=10, w=10
    )

    message_cls = "bg-primary text-primary-foreground" if is_user else "bg-muted"
    align_cls = "justify-end" if is_user else "justify-start"

    # Handle both datetime objects and ISO timestamp strings
    if timestamp:
        if isinstance(timestamp, str):
            # Parse ISO timestamp string from database
            timestamp = datetime.fromisoformat(timestamp)
        time_str = timestamp.strftime("%I:%M %p")
    else:
        time_str = ""

    # Render assistant messages as markdown, user messages as plain text
    if is_user:
        message_body = Div(content, cls=f"rounded-lg p-4 max-w-2xl {message_cls}")
    else:
        # Process MUI tags first
        mui_components, cleaned_content = process_mui_tags(content, session_id)

        # Extract concept tags before markdown processing
        concept_extracted, concept_terms = extract_concept_tags(cleaned_content)

        # Extract LaTeX blocks before markdown processing
        latex_extracted, latex_blocks = extract_latex(concept_extracted)

        # Render markdown with MonsterUI styling (LaTeX and concepts are now safe)
        rendered_md = render_md(latex_extracted)

        # Restore LaTeX blocks after markdown
        rendered_md = restore_latex(rendered_md, latex_blocks)

        # Restore concept links after markdown
        rendered_md = restore_concepts(rendered_md, concept_terms, session_id)

        # Split rendered markdown by HTML comment placeholders and interleave with components
        content_parts = []
        remaining = rendered_md

        for i, component in enumerate(mui_components):
            placeholder = f"<!--MUI_COMPONENT_{i}-->"
            if placeholder in remaining:
                before, remaining = remaining.split(placeholder, 1)
                if before.strip():
                    content_parts.append(Safe(before))
                content_parts.append(component)

        # Add any remaining content
        if remaining.strip():
            content_parts.append(Safe(remaining))

        # If no MUI components, just show rendered markdown
        if not content_parts:
            content_parts = [Safe(rendered_md)]

        message_body = Div(*content_parts, cls=f"rounded-lg p-4 max-w-2xl {message_cls}")

    message_content = DivLAligned(
        avatar if not is_user else None,
        Div(
            message_body,
            Small(time_str, cls=(TextT.muted, "mt-1")) if time_str else None,
            cls="space-y-1"
        ),
        avatar if is_user else None,
        cls=f"flex gap-3 {align_cls}"
    )

    return Div(message_content, cls="mb-4")

def ChatInterface(session_id: str, conversation: list[dict[str, Any]], get_conversation_func: Callable[[str], list[dict[str, Any]]]) -> Any:
    """
    Main chat interface.

    Args:
        session_id: Session identifier
        conversation: Current conversation history
        get_conversation_func: Function to get conversation history

    Returns:
        Chat interface component
    """
    # Chat messages container - show empty state if no messages
    if conversation:
        message_content = [
            *[ChatMessage(msg["role"], msg["content"], msg.get("timestamp"), session_id)
              for msg in conversation],
            Div(id="scroll-anchor")
        ]
    else:
        message_content = [
            EmptyState(),
            Div(id="scroll-anchor")
        ]

    messages = Div(
        *message_content,
        id="chat-messages",
        cls="flex-1 overflow-y-auto p-6 space-y-2"
    )

    # Input form
    chat_form = Form(
        DivLAligned(
            Input(
                id="message-input",
                name="message",
                placeholder="Type your message here...",
                cls="flex-1",
                autofocus=True,
                required=True
            ),
            Button(
                UkIcon("send", cls="mr-2"),
                "Send",
                cls=ButtonT.primary,
                type="submit",
                id="send-btn"
            ),
            cls="gap-2 w-full"
        ),
        id="chat-form",
        hx_post=f"/chat/{session_id}",
        hx_target="#scroll-anchor",
        hx_swap="beforebegin",
        onsubmit="""
            const msg = this.message.value.trim();
            if (!msg) return false;

            // Show user message immediately
            const now = new Date().toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', hour12: true});
            const userMsg = `
                <div class="mb-4">
                    <div class="flex gap-3 justify-end">
                        <div class="space-y-1">
                            <div class="rounded-lg p-4 max-w-2xl bg-primary text-primary-foreground">${msg}</div>
                            <small class="text-muted-foreground mt-1">${now}</small>
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('scroll-anchor').insertAdjacentHTML('beforebegin', userMsg);

            // Show loading indicator
            const loadingMsg = `
                <div class="mb-4" id="loading-indicator">
                    <div class="flex gap-3 justify-start">
                        <div class="space-y-1">
                            <div class="rounded-lg p-4 max-w-2xl bg-muted">
                                <div class="flex items-center gap-2">
                                    <span>Assistant is typing</span>
                                    <span class="loading loading-dots loading-sm"></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('scroll-anchor').insertAdjacentHTML('beforebegin', loadingMsg);

            // Scroll to bottom
            setTimeout(() => {
                const anchor = document.getElementById('scroll-anchor');
                if (anchor) anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }, 100);

            // Clear input
            setTimeout(() => this.reset(), 10);
            return true;
        """,
        cls="p-4 border-t border-border"
    )

    # Header
    header = DivFullySpaced(
        DivLAligned(
            UkIcon("message-circle", height=24, width=24),
            H3("PromptPane Chat"),
            cls="gap-3"
        ),
        Button(
            UkIcon("trash-2", cls="mr-2"),
            "Clear",
            cls=ButtonT.ghost,
            hx_post=f"/clear/{session_id}",
            hx_target="#chat-messages",
            hx_swap="innerHTML"
        ),
        cls="p-4 border-b border-border"
    )

    return Div(
        header,
        messages,
        chat_form,
        Script("""
            // Function to render KaTeX in the chat
            function renderKatexInChat() {
                if (typeof window.katex !== 'undefined' && typeof renderMathInElement !== 'undefined') {
                    try {
                        console.log('Rendering KaTeX...');
                        const chatMessages = document.getElementById('chat-messages');
                        if (chatMessages) {
                            renderMathInElement(chatMessages, {
                                delimiters: [
                                    {left: '$$', right: '$$', display: true},
                                    {left: '$', right: '$', display: false},
                                    {left: '\\\\[', right: '\\\\]', display: true},
                                    {left: '\\\\(', right: '\\\\)', display: false}
                                ],
                                throwOnError: false
                            });
                            console.log('KaTeX rendering complete');
                        }
                    } catch(e) {
                        console.error('KaTeX error:', e);
                    }
                } else {
                    console.log('KaTeX not available, retrying...');
                    setTimeout(renderKatexInChat, 100);
                }
            }

            // Render KaTeX on initial page load
            setTimeout(renderKatexInChat, 100);

            // Global HTMX event listener for all swaps
            document.body.addEventListener('htmx:afterSwap', function(event) {
                console.log('HTMX afterSwap triggered');

                // Remove loading indicator
                const loadingIndicator = document.getElementById('loading-indicator');
                if (loadingIndicator) {
                    console.log('Removing loading indicator');
                    loadingIndicator.remove();
                }

                // Render KaTeX after swap
                setTimeout(renderKatexInChat, 50);

                // Scroll to bottom
                setTimeout(() => {
                    const anchor = document.getElementById('scroll-anchor');
                    if (anchor) {
                        console.log('Scrolling to anchor');
                        anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    }

                    // Refocus input
                    const mainInput = document.getElementById('message-input');
                    if (mainInput) {
                        mainInput.focus();
                    }
                }, 100);
            });
        """),
        cls="flex flex-col h-screen max-w-5xl mx-auto"
    )
