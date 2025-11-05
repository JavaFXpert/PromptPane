"""PromptPane - A chatbot with dynamically generated UI controls using MonsterUI and Groq"""

from fasthtml.common import *
from monsterui.all import *
import os
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv
import re
from html.parser import HTMLParser
from io import StringIO

# Import application constants
from constants import SYSTEM_PROMPT, DEBUG_COMMANDS

# Import utility functions
from utils import (
    extract_citation_urls,
    make_citations_clickable,
    extract_latex,
    restore_latex
)

# Import MUI components and processing
from mui_components import process_mui_tags

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# KaTeX scripts for LaTeX support
katex_css = Link(rel="stylesheet",
                 href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css",
                 integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV",
                 crossorigin="anonymous")

katex_js = Script(src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js",
                  integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8",
                  crossorigin="anonymous")

katex_autorender = Script(src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js",
                          integrity="sha384-+VBxd3r6XgURycqtZ117nYw44OOcIax56Z4dCRWbxyPt0Koah1uHoK0o4+/RRE05",
                          crossorigin="anonymous")

# Custom CSS for citation links
citation_style = Style("""
    .citation-link {
        color: #3b82f6;
        text-decoration: none;
        font-size: 0.85em;
        font-weight: 500;
        padding: 0 2px;
        transition: all 0.2s;
        white-space: nowrap;
    }
    .citation-link:hover {
        color: #1d4ed8;
        text-decoration: underline;
    }
""")

# Create FastHTML app with MonsterUI theme
app, rt = fast_app(
    hdrs=Theme.blue.headers(highlightjs=True) + [katex_css, katex_js, katex_autorender, citation_style],
    live=True
)

# In-memory conversation history (in production, use database)
conversations = {}

def get_conversation(session_id):
    """Get or create conversation history for a session"""
    if session_id not in conversations:
        conversations[session_id] = []
    return conversations[session_id]

def add_message(session_id, role, content):
    """Add a message to conversation history"""
    conversation = get_conversation(session_id)
    conversation.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    })
    return conversation

# ============================================================================
# Error Handling and User Feedback
# ============================================================================

import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_user_friendly_error_message(error):
    """
    Convert technical errors into user-friendly messages.

    Args:
        error: The exception object

    Returns:
        Tuple of (user_message, should_retry)
    """
    error_str = str(error).lower()

    # Rate limiting errors
    if 'rate limit' in error_str or '429' in error_str:
        return (
            "⏳ **Rate Limit Reached**\n\n"
            "The AI service is currently experiencing high demand. "
            "Please wait a moment and try again.\n\n"
            "*Your message has been saved and you can retry by sending it again.*",
            True
        )

    # Authentication errors
    if 'api key' in error_str or 'authentication' in error_str or '401' in error_str or '403' in error_str:
        return (
            "🔑 **Authentication Error**\n\n"
            "There's an issue with the API key configuration. "
            "Please check that your GROQ_API_KEY is set correctly in the `.env` file.\n\n"
            "*Contact the administrator if this problem persists.*",
            False
        )

    # Network/connection errors
    if 'connection' in error_str or 'network' in error_str or 'timeout' in error_str:
        return (
            "🌐 **Connection Issue**\n\n"
            "Unable to reach the AI service. This could be due to:\n"
            "- Network connectivity problems\n"
            "- Service temporarily unavailable\n"
            "- Request timeout\n\n"
            "*Please check your internet connection and try again.*",
            True
        )

    # Service unavailable
    if '503' in error_str or 'service unavailable' in error_str:
        return (
            "🔧 **Service Temporarily Unavailable**\n\n"
            "The AI service is currently down for maintenance or experiencing issues. "
            "Please try again in a few minutes.\n\n"
            "*This is usually temporary and should resolve soon.*",
            True
        )

    # Content policy violations
    if 'content policy' in error_str or 'content filter' in error_str:
        return (
            "⚠️ **Content Policy Violation**\n\n"
            "Your message was flagged by the content policy filter. "
            "Please rephrase your question and try again.\n\n"
            "*Ensure your message follows community guidelines.*",
            False
        )

    # Invalid request
    if 'invalid' in error_str or '400' in error_str:
        return (
            "❌ **Invalid Request**\n\n"
            "There was a problem processing your request. "
            "This might be due to:\n"
            "- Message too long\n"
            "- Invalid characters\n"
            "- Malformed request\n\n"
            "*Try rephrasing your message or making it shorter.*",
            False
        )

    # Model errors
    if 'model' in error_str:
        return (
            "🤖 **Model Error**\n\n"
            "There's an issue with the AI model configuration. "
            "The requested model may be unavailable or deprecated.\n\n"
            "*Contact the administrator to check the model settings.*",
            False
        )

    # Generic error
    logger.error(f"Unexpected error: {error}", exc_info=True)
    return (
        "❌ **Unexpected Error**\n\n"
        "Something went wrong while processing your request. "
        f"Error details: `{str(error)[:100]}`\n\n"
        "*Please try again. If the problem persists, contact support.*",
        True
    )

def retry_with_exponential_backoff(func, max_retries=3, initial_delay=1, max_delay=10):
    """
    Retry a function with exponential backoff for transient failures.

    Args:
        func: Function to retry (should be a callable that takes no arguments)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Result from the function if successful

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()

            # Don't retry non-transient errors
            if any(x in error_str for x in ['api key', 'authentication', '401', '403', 'invalid', '400', 'content policy']):
                logger.warning(f"Non-retryable error on attempt {attempt + 1}: {e}")
                raise

            # Calculate delay with exponential backoff
            delay = min(initial_delay * (2 ** attempt), max_delay)

            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {e}")

    raise last_exception

# ============================================================================
# Debug Commands - For testing error handling from chat interface
# ============================================================================

def is_debug_command(message):
    """Check if message is a debug command"""
    return message.strip() in DEBUG_COMMANDS

def handle_debug_command(message):
    """
    Execute debug command by raising appropriate error.

    Args:
        message: The debug command string

    Raises:
        Appropriate exception based on command
    """
    command = message.strip()

    logger.info(f"Executing debug command: {command}")

    if command == '/test-rate-limit':
        raise Exception("Rate limit exceeded. Error code: 429. Please try again later.")

    elif command == '/test-auth-error':
        raise Exception("Authentication failed. Invalid API key. Error code: 401.")

    elif command == '/test-network-error':
        raise Exception("Connection timeout: Unable to reach the server. Network error occurred.")

    elif command == '/test-service-down':
        raise Exception("Service unavailable. Error code: 503. The service is temporarily down.")

    elif command == '/test-invalid-request':
        raise Exception("Invalid request format. Error code: 400. Bad request.")

    elif command == '/test-model-error':
        raise Exception("Model 'test-invalid-model' not found. Please check model configuration.")

    elif command == '/test-content-policy':
        raise Exception("Content policy violation detected. Your message was flagged by content filter.")

    elif command == '/test-unknown-error':
        raise Exception("An unexpected error occurred in the quantum flux capacitor module.")

    elif command == '/debug-help':
        help_msg = "🔧 **Debug Commands Available:**\n\n"
        for cmd, desc in DEBUG_COMMANDS.items():
            help_msg += f"- `{cmd}` - {desc}\n"
        help_msg += "\n*These commands help test error handling without breaking anything.*"
        return help_msg

    return None

def EmptyState():
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

def ChatMessage(role, content, timestamp=None, session_id="default"):
    """Render a chat message bubble"""
    is_user = role == "user"

    avatar = DiceBearAvatar(
        "User" if is_user else "Assistant",
        h=10, w=10
    )

    message_cls = "bg-primary text-primary-foreground" if is_user else "bg-muted"
    align_cls = "justify-end" if is_user else "justify-start"

    time_str = timestamp.strftime("%I:%M %p") if timestamp else ""

    # Render assistant messages as markdown, user messages as plain text
    if is_user:
        message_body = Div(content, cls=f"rounded-lg p-4 max-w-2xl {message_cls}")
    else:
        # Process MUI tags first
        mui_components, cleaned_content = process_mui_tags(content, session_id)

        # Extract LaTeX blocks before markdown processing
        latex_extracted, latex_blocks = extract_latex(cleaned_content)

        # Render markdown with MonsterUI styling (LaTeX is now safe)
        rendered_md = render_md(latex_extracted)

        # Restore LaTeX blocks after markdown
        rendered_md = restore_latex(rendered_md, latex_blocks)

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

def ChatInterface(session_id="default"):
    """Main chat interface"""
    conversation = get_conversation(session_id)

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

@rt("/")
def get():
    """Main page"""
    return Title("PromptPane"), ChatInterface()

@rt("/chat/{session_id}")
async def post(session_id: str, message: str):
    """Handle chat message submission"""
    if not message.strip():
        conversation = get_conversation(session_id)
        return [ChatMessage(msg["role"], msg["content"], msg.get("timestamp"), session_id)
                for msg in conversation]

    # Add user message
    add_message(session_id, "user", message)

    # Check for debug commands
    if is_debug_command(message):
        # Handle /debug-help separately (doesn't raise error)
        if message.strip() == '/debug-help':
            help_msg = handle_debug_command(message)
            add_message(session_id, "assistant", help_msg)
            conversation = get_conversation(session_id)
            assistant_msg = conversation[-1]
            return ChatMessage(
                assistant_msg["role"],
                assistant_msg["content"],
                assistant_msg.get("timestamp"),
                session_id
            )

    # Get conversation history for context
    conversation = get_conversation(session_id)

    messages_for_api = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[{"role": msg["role"], "content": msg["content"]} for msg in conversation]
    ]

    try:
        # Execute debug command if applicable (will raise error)
        if is_debug_command(message):
            handle_debug_command(message)
        # Define the API call as a function for retry logic
        def make_api_call():
            logger.info(f"Making API call for session {session_id}")
            return client.chat.completions.create(
                messages=messages_for_api,
                model="openai/gpt-oss-120b",
                temperature=0.7,
                # max_tokens=1024,  # Commented out to allow longer responses
                tools=[{"type":"browser_search"},{"type":"code_interpreter"}]
            )

        # Call Groq API with retry logic for transient failures
        chat_completion = retry_with_exponential_backoff(
            make_api_call,
            max_retries=3,
            initial_delay=1,
            max_delay=10
        )

        logger.info(f"API call successful for session {session_id}")

        # Extract citation URLs from tool results
        citation_urls = extract_citation_urls(chat_completion)

        # Get assistant message content
        assistant_message = chat_completion.choices[0].message.content

        # Make citations clickable
        assistant_message = make_citations_clickable(assistant_message, citation_urls)

        # Add assistant response
        add_message(session_id, "assistant", assistant_message)

    except Exception as e:
        # Get user-friendly error message
        error_msg, should_retry = get_user_friendly_error_message(e)

        # Log the error with full details
        logger.error(f"Error in chat endpoint for session {session_id}: {e}", exc_info=True)

        # Add error message to conversation
        add_message(session_id, "assistant", error_msg)

    # Get the assistant's message (the last message in conversation)
    conversation = get_conversation(session_id)
    assistant_msg = conversation[-1]

    # Return only the assistant's message (cleanup handled by hx_on__after_swap)
    return ChatMessage(
        assistant_msg["role"],
        assistant_msg["content"],
        assistant_msg.get("timestamp"),
        session_id
    )

@rt("/clear/{session_id}")
def post(session_id: str):
    """Clear conversation history and return empty chat state"""
    if session_id in conversations:
        conversations[session_id] = []

    # Return the same structure as initial load (reuse EmptyState function)
    return [
        EmptyState(),
        Div(id="scroll-anchor")
    ]

@rt("/send-button/{session_id}")
async def post(session_id: str, message: str):
    """Handle button click - sends the button value as a message"""
    # Add user message (button value)
    add_message(session_id, "user", message)

    # Check for debug commands
    if is_debug_command(message):
        # Handle /debug-help separately (doesn't raise error)
        if message.strip() == '/debug-help':
            help_msg = handle_debug_command(message)
            add_message(session_id, "assistant", help_msg)
            conversation = get_conversation(session_id)
            assistant_msg = conversation[-1]
            return ChatMessage(
                assistant_msg["role"],
                assistant_msg["content"],
                assistant_msg.get("timestamp"),
                session_id
            )

    # Get conversation history
    conversation = get_conversation(session_id)

    messages_for_api = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[{"role": msg["role"], "content": msg["content"]} for msg in conversation]
    ]

    try:
        # Execute debug command if applicable (will raise error)
        if is_debug_command(message):
            handle_debug_command(message)
        # Define the API call as a function for retry logic
        def make_api_call():
            logger.info(f"Making API call for session {session_id} (button)")
            return client.chat.completions.create(
                messages=messages_for_api,
                model="openai/gpt-oss-120b",
                temperature=0.7,
                # max_tokens=1024,  # Commented out to allow longer responses
                tools=[{"type":"browser_search"},{"type":"code_interpreter"}]
            )

        # Call Groq API with retry logic for transient failures
        chat_completion = retry_with_exponential_backoff(
            make_api_call,
            max_retries=3,
            initial_delay=1,
            max_delay=10
        )

        logger.info(f"API call successful for session {session_id} (button)")

        # Extract citation URLs from tool results
        citation_urls = extract_citation_urls(chat_completion)

        # Get assistant message content
        assistant_message = chat_completion.choices[0].message.content

        # Make citations clickable
        assistant_message = make_citations_clickable(assistant_message, citation_urls)

        # Add assistant response
        add_message(session_id, "assistant", assistant_message)

    except Exception as e:
        # Get user-friendly error message
        error_msg, should_retry = get_user_friendly_error_message(e)

        # Log the error with full details
        logger.error(f"Error in send-button endpoint for session {session_id}: {e}", exc_info=True)

        # Add error message to conversation
        add_message(session_id, "assistant", error_msg)

    # Get the assistant's message (the last message in conversation)
    conversation = get_conversation(session_id)
    assistant_msg = conversation[-1]

    # Return only the assistant's message (cleanup handled by hx_on__after_swap)
    return ChatMessage(
        assistant_msg["role"],
        assistant_msg["content"],
        assistant_msg.get("timestamp"),
        session_id
    )

if __name__ == "__main__":
    serve(port=5001)
