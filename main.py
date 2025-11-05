"""PromptPane - A chatbot with dynamically generated UI controls using MonsterUI and Groq"""

from fasthtml.common import *
from monsterui.all import *
import os
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv
from typing import Any

# Import application configuration
import config

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

# Import validators
from validators import (
    validate_chat_request,
    validate_session_id,
    ValidationError,
    SessionIDValidationError,
    MessageValidationError,
    RateLimitError
)

# Initialize Groq client
client = Groq(api_key=config.GROQ_API_KEY)

# KaTeX scripts for LaTeX support
katex_css = Link(
    rel="stylesheet",
    href=config.KATEX_CSS_URL,
    integrity=config.KATEX_CSS_INTEGRITY,
    crossorigin="anonymous"
)

katex_js = Script(
    src=config.KATEX_JS_URL,
    integrity=config.KATEX_JS_INTEGRITY,
    crossorigin="anonymous"
)

katex_autorender = Script(
    src=config.KATEX_AUTORENDER_URL,
    integrity=config.KATEX_AUTORENDER_INTEGRITY,
    crossorigin="anonymous"
)

# Custom CSS for citation links
citation_style = Style(config.CITATION_CSS)

# Create FastHTML app with MonsterUI theme
theme = getattr(Theme, config.THEME_COLOR)
app, rt = fast_app(
    hdrs=theme.headers(highlightjs=config.ENABLE_SYNTAX_HIGHLIGHTING) + [katex_css, katex_js, katex_autorender, citation_style],
    live=config.ENABLE_LIVE_RELOAD
)

# In-memory conversation history (in production, use database)
conversations: dict[str, list[dict[str, Any]]] = {}

def get_conversation(session_id: str) -> list[dict[str, Any]]:
    """Get or create conversation history for a session"""
    if session_id not in conversations:
        conversations[session_id] = []
    return conversations[session_id]

def add_message(session_id: str, role: str, content: str) -> list[dict[str, Any]]:
    """Add a message to conversation history"""
    conversation: list[dict[str, Any]] = get_conversation(session_id)
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
    session_id = config.DEFAULT_SESSION_ID
    conversation = get_conversation(session_id)
    return Title("PromptPane"), ChatInterface(session_id, conversation, get_conversation)

@rt("/chat/{session_id}")
async def post(session_id: str, message: str):
    """Handle chat message submission"""
    # Validate inputs
    try:
        session_id, message = validate_chat_request(session_id, message)
    except RateLimitError as e:
        # Return rate limit error message
        error_msg = f"⏱️ **Rate Limit Exceeded**\n\n{str(e)}"
        add_message(session_id, "assistant", error_msg)
        conversation = get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )
    except MessageValidationError as e:
        # Return message validation error
        error_msg = f"❌ **Invalid Message**\n\n{str(e)}"
        add_message(session_id, "assistant", error_msg)
        conversation = get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )
    except SessionIDValidationError as e:
        # Return session ID validation error
        error_msg = f"❌ **Invalid Session**\n\n{str(e)}"
        logger.error(f"Session ID validation failed: {e}")
        # Can't add to conversation with invalid session ID
        return ChatMessage("assistant", error_msg, datetime.now(), config.DEFAULT_SESSION_ID)
    except ValidationError as e:
        # Generic validation error
        error_msg = f"❌ **Validation Error**\n\n{str(e)}"
        logger.error(f"Validation failed: {e}")
        add_message(session_id, "assistant", error_msg)
        conversation = get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )

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
                model=config.GROQ_MODEL,
                temperature=config.GROQ_TEMPERATURE,
                # max_tokens=1024,  # Commented out to allow longer responses
                tools=config.GROQ_TOOLS
            )

        # Call Groq API with retry logic for transient failures
        chat_completion = retry_with_exponential_backoff(
            make_api_call,
            max_retries=config.RETRY_MAX_ATTEMPTS,
            initial_delay=config.RETRY_INITIAL_DELAY,
            max_delay=config.RETRY_MAX_DELAY
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
    # Validate session ID
    try:
        session_id = validate_session_id(session_id)
    except SessionIDValidationError as e:
        logger.error(f"Invalid session ID in clear route: {e}")
        # Return empty state with default session
        return [
            EmptyState(),
            Div(id="scroll-anchor")
        ]

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
    # Validate inputs
    try:
        session_id, message = validate_chat_request(session_id, message)
    except RateLimitError as e:
        # Return rate limit error message
        error_msg = f"⏱️ **Rate Limit Exceeded**\n\n{str(e)}"
        add_message(session_id, "assistant", error_msg)
        conversation = get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )
    except MessageValidationError as e:
        # Return message validation error
        error_msg = f"❌ **Invalid Message**\n\n{str(e)}"
        add_message(session_id, "assistant", error_msg)
        conversation = get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )
    except SessionIDValidationError as e:
        # Return session ID validation error
        error_msg = f"❌ **Invalid Session**\n\n{str(e)}"
        logger.error(f"Session ID validation failed: {e}")
        return ChatMessage("assistant", error_msg, datetime.now(), config.DEFAULT_SESSION_ID)
    except ValidationError as e:
        # Generic validation error
        error_msg = f"❌ **Validation Error**\n\n{str(e)}"
        logger.error(f"Validation failed: {e}")
        add_message(session_id, "assistant", error_msg)
        conversation = get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )

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
                model=config.GROQ_MODEL,
                temperature=config.GROQ_TEMPERATURE,
                # max_tokens=1024,  # Commented out to allow longer responses
                tools=config.GROQ_TOOLS
            )

        # Call Groq API with retry logic for transient failures
        chat_completion = retry_with_exponential_backoff(
            make_api_call,
            max_retries=config.RETRY_MAX_ATTEMPTS,
            initial_delay=config.RETRY_INITIAL_DELAY,
            max_delay=config.RETRY_MAX_DELAY
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
    serve(port=config.SERVER_PORT)
