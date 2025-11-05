"""PromptPane - A chatbot with dynamically generated UI controls using MonsterUI and Groq"""

from fasthtml.common import *
from monsterui.all import *
import os
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv

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

# Import error handling functions
from error_handling import (
    get_user_friendly_error_message,
    retry_with_exponential_backoff,
    is_debug_command,
    handle_debug_command,
    logger
)

# Import UI components
from ui_components import (
    EmptyState,
    ChatMessage,
    ChatInterface
)

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
# Routes
# ============================================================================

@rt("/")
def get():
    """Main page"""
    session_id = "default"
    conversation = get_conversation(session_id)
    return Title("PromptPane"), ChatInterface(session_id, conversation, get_conversation)

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
