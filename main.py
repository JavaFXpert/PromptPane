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

# Import database module
import db

# Import entity extraction module
from entity_extraction import (
    extract_entities_from_conversation,
    should_extract_entities
)

# Import knowledge graph manager
from knowledge_graph_manager import (
    update_knowledge_graph_with_llm,
    build_context_from_kg,
    load_knowledge_graph,
    save_knowledge_graph
)

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

# Import session UI components
from session_ui_components import (
    SessionSidebar,
    SessionListItem,
    NewSessionModal,
    SessionRenameInlineForm
)

# Import entity UI components
from entity_ui_components import (
    EntitySidebar,
    EntityListItem,
    EntityEditForm,
    EmptyEntityState
)

# Import learning objectives manager
from learning_objectives_manager import (
    load_learning_objectives,
    save_learning_objectives,
    get_active_objective,
    set_active_objective,
    clear_active_objective,
    decompose_objective_with_llm,
    update_mastery_with_llm,
    format_objectives_for_prompt,
    build_objectives_context
)

# Import learning objectives UI components
from learning_objectives_ui_components import (
    ObjectiveSidebar,
    ObjectiveTreeItem,
    NoActiveObjectiveState,
    ReplaceObjectiveConfirmationModal,
    ObjectiveSummaryCard
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

# ============================================================================
# Routes
# ============================================================================

@rt("/")
def get():
    """Main page"""
    session_id = config.DEFAULT_SESSION_ID

    # Ensure default session metadata exists
    db.ensure_session_metadata_exists(session_id, "Default Session")

    # Update last accessed time
    db.update_session_access(session_id)

    # Get conversation
    conversation = db.get_conversation(session_id)

    # Get all sessions for sidebar
    sessions = db.get_all_session_metadata()

    # Get all entities from JSON knowledge graph for entity sidebar
    kg = load_knowledge_graph()
    entities = kg.get("entities", [])

    # Get active learning objective for objectives sidebar
    active_objective = get_active_objective()

    # Create tabbed right sidebar combining Knowledge Graph and Learning Path
    right_sidebar = Div(
        # Tabs header
        Div(
            Button(
                "Knowledge Graph",
                cls="tab tab-lifted tab-active",
                hx_get="/sidebar/knowledge-graph",
                hx_target="#right-sidebar-content",
                hx_swap="innerHTML",
                onclick="switchTab(event, 'knowledge-graph')"
            ),
            Button(
                "Learning Path",
                cls="tab tab-lifted",
                hx_get="/sidebar/learning-path",
                hx_target="#right-sidebar-content",
                hx_swap="innerHTML",
                onclick="switchTab(event, 'learning-path')"
            ),
            cls="tabs tabs-lifted",
            role="tablist"
        ),
        # Tab content (initially shows Knowledge Graph)
        Div(
            EntitySidebar(entities),
            id="right-sidebar-content",
            cls="flex-1 overflow-hidden"
        ),
        # JavaScript for tab switching
        Script("""
function switchTab(event, tabName) {
    // Remove active class from all tabs
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => tab.classList.remove('tab-active'));

    // Add active class to clicked tab
    event.target.classList.add('tab-active');
}
        """),
        cls="w-80 bg-base-100 border-l border-base-300 flex flex-col"
    )

    # Return full page with session sidebar (left), chat (center), tabbed sidebar (right)
    return Title("PromptPane"), Div(
        SessionSidebar(sessions, session_id),
        ChatInterface(session_id, conversation, db.get_conversation),
        right_sidebar,
        cls="flex h-screen"
    )

@rt("/chat/{session_id}")
async def post(session_id: str, message: str):
    """Handle chat message submission"""
    # Validate inputs
    try:
        session_id, message = validate_chat_request(session_id, message)
    except RateLimitError as e:
        # Return rate limit error message
        error_msg = f"⏱️ **Rate Limit Exceeded**\n\n{str(e)}"
        db.add_message(session_id, "assistant", error_msg)
        conversation = db.get_conversation(session_id)
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
        db.add_message(session_id, "assistant", error_msg)
        conversation = db.get_conversation(session_id)
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
        db.add_message(session_id, "assistant", error_msg)
        conversation = db.get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )

    # Check if session exists - don't allow messaging deleted sessions
    if not db.get_session(session_id):
        # Session was deleted or doesn't exist
        error_msg = "❌ **Session Not Found**\n\nThis session has been deleted. Redirecting to default session..."
        logger.warning(f"Attempted to message deleted session: {session_id}")
        # Return error and use HX-Redirect to send user to default session
        return Response(
            str(ChatMessage("assistant", error_msg, datetime.now(), config.DEFAULT_SESSION_ID)),
            headers={"HX-Redirect": "/"}
        )

    # Add user message
    db.add_message(session_id, "user", message)

    # Update session metadata
    db.update_session_access(session_id)
    db.update_session_message_count(session_id)

    # Check for debug commands
    if is_debug_command(message):
        # Handle /debug-help separately (doesn't raise error)
        if message.strip() == '/debug-help':
            help_msg = handle_debug_command(message)
            db.add_message(session_id, "assistant", help_msg)
            conversation = db.get_conversation(session_id)
            assistant_msg = conversation[-1]
            return ChatMessage(
                assistant_msg["role"],
                assistant_msg["content"],
                assistant_msg.get("timestamp"),
                session_id
            )

    # Check for learning intent and create objective if detected
    if config.ENABLE_LEARNING_OBJECTIVES:
        learning_phrases = [
            "i want to learn",
            "teach me",
            "help me learn",
            "help me understand",
            "i'd like to learn",
            "i would like to learn",
            "explain how to",
            "show me how to"
        ]

        message_lower = message.lower()
        is_learning_intent = any(phrase in message_lower for phrase in learning_phrases)

        if is_learning_intent:
            try:
                # Extract topic (everything after the learning phrase)
                topic = message
                for phrase in learning_phrases:
                    if phrase in message_lower:
                        # Find the phrase and extract what comes after
                        idx = message_lower.index(phrase)
                        topic = message[idx + len(phrase):].strip()
                        break

                # Clean up common words at the start
                topic = topic.lstrip("about how to the ")

                logger.info(f"Learning intent detected for topic: {topic}")

                # Check if there's an existing objective
                existing_objective = get_active_objective()

                # If there's an existing objective, ask for confirmation
                if existing_objective:
                    confirmation_message = f"📚 I can create a learning path for **{topic}**!\n\n"
                    confirmation_message += f"⚠️ **Note**: You currently have an active learning path:\n"
                    confirmation_message += f"**\"{existing_objective['title']}\"**\n\n"
                    confirmation_message += f"Creating a new path will **completely replace** your current one.\n\n"
                    confirmation_message += "Would you like to proceed?\n\n"
                    confirmation_message += f'<mui type="buttons">\n'
                    confirmation_message += f'<option value="CONFIRM_CREATE_OBJECTIVE:{topic}">Yes, replace with new path</option>\n'
                    confirmation_message += f'<option value="CANCEL_CREATE_OBJECTIVE">No, keep current path</option>\n'
                    confirmation_message += f'</mui>'

                    db.add_message(session_id, "assistant", confirmation_message)
                    conversation = db.get_conversation(session_id)
                    assistant_msg = conversation[-1]
                    return ChatMessage(
                        assistant_msg["role"],
                        assistant_msg["content"],
                        assistant_msg.get("timestamp"),
                        session_id
                    )

                # No existing objective, proceed directly
                ack_message = f"Excellent! I'll create a structured learning path for **{topic}**.\n\n"
                ack_message += "Give me a moment to break this down into manageable objectives..."

                # Add acknowledgment message
                db.add_message(session_id, "assistant", ack_message)

                # Decompose the objective using LLM
                objective = decompose_objective_with_llm(
                    title=f"Learn {topic}",
                    description=f"Master the fundamentals and advanced concepts of {topic}",
                    client=client,
                    parent_id=None,
                    current_depth=0
                )

                # Set as active objective (archive existing)
                set_active_objective(objective, archive_existing=True)

                logger.info(f"Created learning objective: {objective['title']}")

                # Add success message with summary
                success_message = f"✅ **Learning Path Created!**\n\n"
                success_message += f"I've created a comprehensive learning path for **{topic}** with {len(objective.get('children', []))} main areas.\n\n"
                success_message += "Check the **Learning Path** tab in the right sidebar to see the full hierarchy. "
                success_message += "I'll track your progress as we go!\n\n"
                success_message += f"Let's start with the first topic: **{objective['children'][0]['title']}**" if objective.get('children') else "Let's begin!"

                db.add_message(session_id, "assistant", success_message)

                # Return both messages
                conversation = db.get_conversation(session_id)
                # Return the last assistant message (success message)
                assistant_msg = conversation[-1]
                return ChatMessage(
                    assistant_msg["role"],
                    assistant_msg["content"],
                    assistant_msg.get("timestamp"),
                    session_id
                )

            except Exception as e:
                logger.error(f"Failed to create learning objective: {e}", exc_info=True)
                error_msg = f"I detected that you want to learn about **{topic}**, but I encountered an error creating the learning path: {str(e)}\n\nLet's continue with a regular conversation instead."
                db.add_message(session_id, "assistant", error_msg)
                conversation = db.get_conversation(session_id)
                assistant_msg = conversation[-1]
                return ChatMessage(
                    assistant_msg["role"],
                    assistant_msg["content"],
                    assistant_msg.get("timestamp"),
                    session_id
                )

    # Get conversation history for context
    conversation = db.get_conversation(session_id)

    # Build system prompt with knowledge graph context and learning objectives
    system_prompt = SYSTEM_PROMPT
    if config.ENABLE_ENTITY_EXTRACTION:
        # Use JSON-based knowledge graph for context
        kg_context = build_context_from_kg(
            kg=None,  # Will load from file
            max_entities=config.ENTITY_CONTEXT_MAX_ENTITIES,
            min_confidence=config.ENTITY_CONTEXT_MIN_CONFIDENCE
        )
        if kg_context:
            system_prompt = f"{SYSTEM_PROMPT}\n\n{kg_context}"

    # Add learning objectives context
    if config.ENABLE_LEARNING_OBJECTIVES:
        objectives_context = build_objectives_context()
        if objectives_context:
            system_prompt = f"{system_prompt}\n\n{objectives_context}"

    messages_for_api = [
        {"role": "system", "content": system_prompt},
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
        db.add_message(session_id, "assistant", assistant_message)

        # Update knowledge graph using LLM-based curation
        if config.ENABLE_ENTITY_EXTRACTION:
            if should_extract_entities(message, assistant_message):
                try:
                    # Load current knowledge graph
                    current_kg = load_knowledge_graph()

                    # Update knowledge graph with LLM (handles deduplication semantically)
                    updated_kg = update_knowledge_graph_with_llm(
                        user_message=message,
                        assistant_response=assistant_message,
                        client=client,
                        current_kg=current_kg
                    )

                    if updated_kg:
                        logger.info(f"Knowledge graph updated: {len(updated_kg.get('entities', []))} entities, {len(updated_kg.get('relationships', []))} relationships")

                        # Optional: Sync updated entities back to database for UI
                        # This keeps the database as a cache/view of the JSON source of truth
                        # (We can implement this sync later if needed)
                    else:
                        logger.warning("Knowledge graph update failed validation, keeping old version")

                except Exception as e:
                    # Don't fail the request if knowledge graph update fails
                    logger.error(f"Knowledge graph update failed: {e}", exc_info=True)

        # Update learning objectives mastery using LLM-based assessment
        if config.ENABLE_LEARNING_OBJECTIVES and config.ENABLE_AUTO_MASTERY_TRACKING:
            active_objective = get_active_objective()
            if active_objective:
                try:
                    # Get recent conversation for mastery assessment
                    recent_conversation = conversation[-6:]  # Last 6 messages

                    # Update mastery levels based on conversation
                    updates = update_mastery_with_llm(
                        conversation_context=recent_conversation,
                        objective_tree=active_objective,
                        client=client
                    )

                    if updates:
                        logger.info(f"Updated {len(updates)} objective mastery levels")

                except Exception as e:
                    # Don't fail the request if mastery update fails
                    logger.error(f"Mastery update failed: {e}", exc_info=True)

    except Exception as e:
        # Get user-friendly error message
        error_msg, should_retry = get_user_friendly_error_message(e)

        # Log the error with full details
        logger.error(f"Error in chat endpoint for session {session_id}: {e}", exc_info=True)

        # Add error message to conversation
        db.add_message(session_id, "assistant", error_msg)

    # Get the assistant's message (the last message in conversation)
    conversation = db.get_conversation(session_id)
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

    # Clear conversation from database
    db.clear_conversation(session_id)

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
        db.add_message(session_id, "assistant", error_msg)
        conversation = db.get_conversation(session_id)
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
        db.add_message(session_id, "assistant", error_msg)
        conversation = db.get_conversation(session_id)
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
        db.add_message(session_id, "assistant", error_msg)
        conversation = db.get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )

    # Check if session exists - don't allow messaging deleted sessions
    if not db.get_session(session_id):
        # Session was deleted or doesn't exist
        error_msg = "❌ **Session Not Found**\n\nThis session has been deleted. Redirecting to default session..."
        logger.warning(f"Attempted to use button in deleted session: {session_id}")
        # Return error and use HX-Redirect to send user to default session
        return Response(
            str(ChatMessage("assistant", error_msg, datetime.now(), config.DEFAULT_SESSION_ID)),
            headers={"HX-Redirect": "/"}
        )

    # Add user message (button value)
    db.add_message(session_id, "user", message)

    # Update session metadata
    db.update_session_access(session_id)
    db.update_session_message_count(session_id)

    # Check for learning objective confirmation buttons
    if message.startswith("CONFIRM_CREATE_OBJECTIVE:"):
        topic = message.replace("CONFIRM_CREATE_OBJECTIVE:", "").strip()
        logger.info(f"User confirmed creation of learning objective for: {topic}")

        try:
            ack_message = f"Perfect! Creating your learning path for **{topic}**...\n\nThis may take a moment."
            db.add_message(session_id, "assistant", ack_message)

            # Decompose the objective using LLM
            objective = decompose_objective_with_llm(
                title=f"Learn {topic}",
                description=f"Master the fundamentals and advanced concepts of {topic}",
                client=client,
                parent_id=None,
                current_depth=0
            )

            # Set as active objective (archive existing)
            set_active_objective(objective, archive_existing=True)

            logger.info(f"Created learning objective: {objective['title']}")

            # Add success message with sidebar refresh trigger
            success_message = f"✅ **Learning Path Created!**\n\n"
            success_message += f"I've created a comprehensive learning path for **{topic}** with {len(objective.get('children', []))} main areas.\n\n"
            success_message += "👉 Check the **Learning Path** tab in the right sidebar to see the full hierarchy.\n\n"
            success_message += "I'll track your progress as we go!\n\n"
            success_message += f"Let's start with: **{objective['children'][0]['title']}**" if objective.get('children') else "Let's begin!"

            db.add_message(session_id, "assistant", success_message)

            # Return success message with script to refresh sidebar
            conversation = db.get_conversation(session_id)
            assistant_msg = conversation[-1]

            # Add JavaScript to trigger sidebar refresh
            refresh_script = Script("""
                // Trigger learning path sidebar refresh
                htmx.ajax('GET', '/sidebar/learning-path', {target:'#right-sidebar-content', swap:'innerHTML'});
            """)

            return Div(
                ChatMessage(
                    assistant_msg["role"],
                    assistant_msg["content"],
                    assistant_msg.get("timestamp"),
                    session_id
                ),
                refresh_script
            )

        except Exception as e:
            logger.error(f"Failed to create learning objective: {e}", exc_info=True)
            error_msg = f"I encountered an error creating the learning path: {str(e)}\n\nPlease try again."
            db.add_message(session_id, "assistant", error_msg)
            conversation = db.get_conversation(session_id)
            assistant_msg = conversation[-1]
            return ChatMessage(
                assistant_msg["role"],
                assistant_msg["content"],
                assistant_msg.get("timestamp"),
                session_id
            )

    elif message == "CANCEL_CREATE_OBJECTIVE":
        logger.info("User cancelled creation of learning objective")
        cancel_message = "No problem! Your current learning path remains active. Let me know if you'd like to work on your current objectives or if you need anything else!"
        db.add_message(session_id, "assistant", cancel_message)
        conversation = db.get_conversation(session_id)
        assistant_msg = conversation[-1]
        return ChatMessage(
            assistant_msg["role"],
            assistant_msg["content"],
            assistant_msg.get("timestamp"),
            session_id
        )

    # Check for debug commands
    if is_debug_command(message):
        # Handle /debug-help separately (doesn't raise error)
        if message.strip() == '/debug-help':
            help_msg = handle_debug_command(message)
            db.add_message(session_id, "assistant", help_msg)
            conversation = db.get_conversation(session_id)
            assistant_msg = conversation[-1]
            return ChatMessage(
                assistant_msg["role"],
                assistant_msg["content"],
                assistant_msg.get("timestamp"),
                session_id
            )

    # Get conversation history
    conversation = db.get_conversation(session_id)

    # Build system prompt with knowledge graph context and learning objectives
    system_prompt = SYSTEM_PROMPT
    if config.ENABLE_ENTITY_EXTRACTION:
        # Use JSON-based knowledge graph for context
        kg_context = build_context_from_kg(
            kg=None,  # Will load from file
            max_entities=config.ENTITY_CONTEXT_MAX_ENTITIES,
            min_confidence=config.ENTITY_CONTEXT_MIN_CONFIDENCE
        )
        if kg_context:
            system_prompt = f"{SYSTEM_PROMPT}\n\n{kg_context}"

    # Add learning objectives context
    if config.ENABLE_LEARNING_OBJECTIVES:
        objectives_context = build_objectives_context()
        if objectives_context:
            system_prompt = f"{system_prompt}\n\n{objectives_context}"

    messages_for_api = [
        {"role": "system", "content": system_prompt},
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
        db.add_message(session_id, "assistant", assistant_message)

        # Update knowledge graph using LLM-based curation
        if config.ENABLE_ENTITY_EXTRACTION:
            if should_extract_entities(message, assistant_message):
                try:
                    # Load current knowledge graph
                    current_kg = load_knowledge_graph()

                    # Update knowledge graph with LLM (handles deduplication semantically)
                    updated_kg = update_knowledge_graph_with_llm(
                        user_message=message,
                        assistant_response=assistant_message,
                        client=client,
                        current_kg=current_kg
                    )

                    if updated_kg:
                        logger.info(f"Knowledge graph updated: {len(updated_kg.get('entities', []))} entities, {len(updated_kg.get('relationships', []))} relationships")

                        # Optional: Sync updated entities back to database for UI
                        # This keeps the database as a cache/view of the JSON source of truth
                        # (We can implement this sync later if needed)
                    else:
                        logger.warning("Knowledge graph update failed validation, keeping old version")

                except Exception as e:
                    # Don't fail the request if knowledge graph update fails
                    logger.error(f"Knowledge graph update failed: {e}", exc_info=True)

        # Update learning objectives mastery using LLM-based assessment
        if config.ENABLE_LEARNING_OBJECTIVES and config.ENABLE_AUTO_MASTERY_TRACKING:
            active_objective = get_active_objective()
            if active_objective:
                try:
                    # Get recent conversation for mastery assessment
                    recent_conversation = conversation[-6:]  # Last 6 messages

                    # Update mastery levels based on conversation
                    updates = update_mastery_with_llm(
                        conversation_context=recent_conversation,
                        objective_tree=active_objective,
                        client=client
                    )

                    if updates:
                        logger.info(f"Updated {len(updates)} objective mastery levels")

                except Exception as e:
                    # Don't fail the request if mastery update fails
                    logger.error(f"Mastery update failed: {e}", exc_info=True)

    except Exception as e:
        # Get user-friendly error message
        error_msg, should_retry = get_user_friendly_error_message(e)

        # Log the error with full details
        logger.error(f"Error in send-button endpoint for session {session_id}: {e}", exc_info=True)

        # Add error message to conversation
        db.add_message(session_id, "assistant", error_msg)

    # Get the assistant's message (the last message in conversation)
    conversation = db.get_conversation(session_id)
    assistant_msg = conversation[-1]

    # Return only the assistant's message (cleanup handled by hx_on__after_swap)
    return ChatMessage(
        assistant_msg["role"],
        assistant_msg["content"],
        assistant_msg.get("timestamp"),
        session_id
    )


@rt("/explain-concept/{session_id}")
async def post(session_id: str, concept: str):
    """
    Handle concept explanation requests from clickable concept links.

    When a user clicks a <concept> link in the chat, this endpoint:
    1. Adds a user message: "🔍 Explain: {concept}"
    2. Sends the concept to the LLM with instructions to explain briefly
    3. Returns the explanation as an assistant message

    Args:
        session_id: Current session identifier
        concept: The concept term to explain

    Returns:
        ChatMessage component with the explanation
    """
    # Validate inputs
    session_id, concept = validate_chat_request(session_id, concept)

    # Create user message for the concept query
    user_message = f"🔍 Explain: {concept}"
    db.add_message(session_id, "user", user_message)

    # Get conversation history
    conversation = db.get_conversation(session_id)

    # Build context from knowledge graph
    kg_context = build_context_from_kg()

    # Build system prompt with special instruction for concept explanations
    system_prompt_with_instruction = f"""{SYSTEM_PROMPT}

IMPORTANT - For this concept explanation:
- Provide a brief, beginner-friendly explanation (2-4 sentences)
- MUST mark 2-3 related technical terms with <concept>term</concept> tags for further exploration
- Keep it concise but clear
- Use examples if helpful
- Example: "A <concept>compiler</concept> translates <concept>source code</concept> into <concept>machine code</concept>."

{kg_context}"""

    # Build messages for API
    messages_for_api = [
        {"role": "system", "content": system_prompt_with_instruction}
    ]

    # Add conversation history
    for msg in conversation:
        messages_for_api.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Call Groq API
    try:
        chat_completion = client.chat.completions.create(
            messages=messages_for_api,
            model=config.GROQ_MODEL,
            temperature=0.7,  # Standard temperature (was 0.5, increased to encourage concept tagging)
            max_tokens=500    # Limit length for brief explanations
        )

        explanation = chat_completion.choices[0].message.content

        # DEBUG: Log raw LLM response
        print(f"[DEBUG /explain-concept] Raw LLM response for '{concept}':")
        print(f"[DEBUG /explain-concept] {explanation}")
        print(f"[DEBUG /explain-concept] Contains <concept> tags: {'<concept>' in explanation}")

        # Check if explanation was successful
        if not explanation or explanation.strip() == "":
            explanation = f"I apologize, but I don't have enough information to explain '{concept}' clearly. Could you provide more context?"

    except Exception as e:
        logger.error(f"Error getting concept explanation: {e}")
        explanation = f"I encountered an error while trying to explain '{concept}'. Please try again."

    # Add assistant's explanation to conversation
    db.add_message(session_id, "assistant", explanation)

    # Update knowledge graph with this interaction
    try:
        update_knowledge_graph_with_llm(user_message, explanation, client)
    except Exception as e:
        logger.error(f"Failed to update knowledge graph: {e}")

    # Get the updated conversation and return the assistant's message
    conversation = db.get_conversation(session_id)
    assistant_msg = conversation[-1]

    return ChatMessage(
        assistant_msg["role"],
        assistant_msg["content"],
        assistant_msg.get("timestamp"),
        session_id
    )


@rt("/request-video/{session_id}")
async def post(session_id: str, subject: str = ""):
    """
    Handle video request button clicks.

    When a user clicks the Video button:
    1. If subject is provided, use that as the video topic
    2. If subject is empty, analyze recent conversation to determine the topic
    3. Ask the LLM to find a highly rated, short YouTube video on that topic

    Args:
        session_id: Current session identifier
        subject: Optional subject for the video (from message input)

    Returns:
        ChatMessage component with the video
    """
    # Validate inputs
    session_id = validate_session_id(session_id)

    # Get conversation history
    conversation = db.get_conversation(session_id)

    # Determine the video subject
    if subject and subject.strip():
        # User provided a specific subject
        user_message = f"🎥 Show me a video about: {subject.strip()}"
        video_topic = subject.strip()
    else:
        # Use conversation context to determine subject
        user_message = "🎥 Show me a video on the current topic"

        # Analyze recent messages to extract the topic
        recent_messages = conversation[-5:] if len(conversation) >= 5 else conversation
        context = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in recent_messages])

        # Ask LLM to identify the topic
        try:
            topic_response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": f"""Based on this recent conversation, identify the main topic or subject being discussed in 2-5 words.

Recent conversation:
{context}

Respond with ONLY the topic/subject (e.g., "derivatives in calculus", "Python programming", "Italian cuisine").
No explanations, just the topic."""}
                ],
                model=config.GROQ_MODEL,
                temperature=0.3,
                max_tokens=50
            )

            video_topic = topic_response.choices[0].message.content.strip()
            logger.info(f"Identified video topic from context: {video_topic}")

        except Exception as e:
            logger.error(f"Error identifying topic: {e}")
            video_topic = "the current subject"

    # Add user message to conversation
    db.add_message(session_id, "user", user_message)

    # Build context from knowledge graph
    kg_context = build_context_from_kg()

    # Build system prompt for video request
    system_prompt_with_instruction = f"""{SYSTEM_PROMPT}

CRITICAL - Video Request:
The user clicked the Video button requesting a YouTube video about: {video_topic}

YOU MUST:
1. Use browser_search to find a highly rated YouTube video (5-15 minutes) about "{video_topic}"
2. Search query example: "best short youtube video explaining {video_topic}"
3. ALWAYS embed the video using: <mui type="video" url="YOUTUBE_URL_HERE" caption="Video title">
4. Provide a brief 1-2 sentence introduction BEFORE the video tag
5. Include 2-3 related <concept> links AFTER the video for further exploration

REQUIRED FORMAT:
Here's a great video that explains [topic]:

<mui type="video" url="https://www.youtube.com/watch?v=VIDEO_ID" caption="Video Title - Duration">
</mui>

Related concepts: <concept>term1</concept>, <concept>term2</concept>

DO NOT respond without including a video. The user specifically requested a video.

{kg_context}"""

    # Build messages for API
    messages_for_api = [
        {"role": "system", "content": system_prompt_with_instruction}
    ]

    # Add recent conversation history for context (last 5 messages)
    recent_conv = conversation[-5:] if len(conversation) >= 5 else conversation
    for msg in recent_conv:
        messages_for_api.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Call Groq API with tools enabled (browser_search for finding videos)
    try:
        chat_completion = client.chat.completions.create(
            messages=messages_for_api,
            model=config.GROQ_MODEL,
            temperature=0.7,
            max_tokens=1000,
            tools=config.GROQ_TOOLS  # Enable browser_search to find YouTube videos
        )

        video_response = chat_completion.choices[0].message.content

        # Check if response was successful
        if not video_response or video_response.strip() == "":
            video_response = f"I apologize, but I couldn't find a suitable video about '{video_topic}'. Please try searching directly on YouTube."

        # Validate that response includes a video tag
        if '<mui type="video"' not in video_response:
            logger.warning(f"LLM response for video request did not include video tag. Response: {video_response[:200]}")
            # Add a helpful message if no video was included
            video_response = f"I apologize, but I wasn't able to find a suitable video about '{video_topic}' at the moment. You can search directly on YouTube for: **{video_topic} tutorial**\n\nWould you like me to help with something else related to {video_topic}?"

    except Exception as e:
        logger.error(f"Error getting video recommendation: {e}")
        video_response = f"I encountered an error while searching for a video about '{video_topic}'. Please try again."

    # Add assistant's response to conversation
    db.add_message(session_id, "assistant", video_response)

    # Update knowledge graph if needed
    try:
        update_knowledge_graph_with_llm(user_message, video_response, client)
    except Exception as e:
        logger.error(f"Failed to update knowledge graph: {e}")

    # Get the updated conversation and return the assistant's message
    conversation = db.get_conversation(session_id)
    assistant_msg = conversation[-1]

    return ChatMessage(
        assistant_msg["role"],
        assistant_msg["content"],
        assistant_msg.get("timestamp"),
        session_id
    )

# ============================================================================
# Session Management Routes
# ============================================================================

@rt("/session/new")
def post():
    """Create a new session"""
    import uuid

    # Generate unique session ID
    session_id = f"session-{uuid.uuid4().hex[:12]}"

    # Create session metadata with temporary name
    db.create_session(session_id, "New Session", "💬")

    # Update access time
    db.update_session_access(session_id)

    # Redirect to new session
    return RedirectResponse(f"/session/{session_id}/switch", status_code=303)


@rt("/session/{session_id}/switch")
def get(session_id: str):
    """Switch to a different session"""
    # Validate session ID
    try:
        session_id = validate_session_id(session_id)
    except SessionIDValidationError:
        # Redirect to default session if invalid
        return RedirectResponse("/", status_code=303)

    # Check if session exists - if not, redirect to default
    # (Don't auto-create deleted sessions)
    if not db.get_session(session_id):
        logger.info(f"Session {session_id} does not exist, redirecting to default")
        return RedirectResponse("/", status_code=303)

    # Update last accessed time
    db.update_session_access(session_id)

    # Get conversation
    conversation = db.get_conversation(session_id)

    # Get all sessions for sidebar
    sessions = db.get_all_session_metadata()

    # Get all entities from JSON knowledge graph for entity sidebar
    kg = load_knowledge_graph()
    entities = kg.get("entities", [])

    # Return full page with session sidebar (left), chat (center), entity sidebar (right)
    return Title("PromptPane"), Div(
        SessionSidebar(sessions, session_id),
        ChatInterface(session_id, conversation, db.get_conversation),
        EntitySidebar(entities),
        cls="flex h-screen"
    )


@rt("/session/{session_id}/delete")
def delete(session_id: str):
    """Delete a session and all its data"""
    logger.info(f"DELETE route called for session: {session_id}")

    # Validate session ID
    try:
        session_id = validate_session_id(session_id)
        logger.info(f"Session ID validated: {session_id}")
    except SessionIDValidationError as e:
        logger.error(f"Session ID validation failed: {e}")
        return Div()  # Return empty if invalid

    # Don't allow deleting default session
    if session_id == config.DEFAULT_SESSION_ID:
        logger.warning(f"Attempted to delete default session")
        return Div()

    # Delete session
    logger.info(f"About to delete session from database: {session_id}")
    deleted_count = db.delete_session(session_id)
    logger.info(f"Deleted session: {session_id}, records deleted: {deleted_count}")

    # Use HTMX redirect header to redirect to default session
    # This tells HTMX to do a full page redirect instead of swapping content
    logger.info(f"Returning HX-Redirect to /")
    return Response(
        "",
        headers={"HX-Redirect": "/"}
    )


@rt("/session/{session_id}/rename-form")
def get(session_id: str):
    """Get inline rename form for a session"""
    try:
        session_id = validate_session_id(session_id)
    except SessionIDValidationError:
        return Div()

    session = db.get_session(session_id)
    if not session:
        return Div()

    return SessionRenameInlineForm(session)


@rt("/session/{session_id}/rename-cancel")
def get(session_id: str):
    """Cancel rename and restore original session name"""
    try:
        session_id = validate_session_id(session_id)
    except SessionIDValidationError:
        return Div()

    session = db.get_session(session_id)
    if not session:
        return Div()

    # Return just the session name div (the part that was replaced)
    return Div(
        session["name"],
        cls="font-semibold text-sm cursor-pointer",
        hx_get=f"/session/{session_id}/switch",
        hx_target="body",
        hx_swap="outerHTML",
        id=f"session-name-{session_id}"
    )


@rt("/session/{session_id}/rename")
def put(session_id: str, name: str):
    """Rename a session"""
    # Validate session ID and name
    try:
        session_id = validate_session_id(session_id)
    except SessionIDValidationError:
        return Div()

    if not name or len(name) > 100:
        return Div()

    # Update session name
    db.update_session_name(session_id, name)

    # Get updated session
    session = db.get_session(session_id)

    # Return updated session item
    return SessionListItem(session, session_id)


@rt("/session/{session_id}/finalize")
def post(session_id: str, name: str, icon: str = "💬"):
    """Finalize new session with custom name and icon"""
    # Validate inputs
    try:
        session_id = validate_session_id(session_id)
    except SessionIDValidationError:
        return RedirectResponse("/", status_code=303)

    if not name or len(name) > 100:
        name = f"Session {session_id[:8]}"

    # Update session metadata
    db.update_session_name(session_id, name)
    db.update_session_icon(session_id, icon)

    # Redirect to the session
    return RedirectResponse(f"/session/{session_id}/switch", status_code=303)


# ============================================================================
# Entity Management Routes
# ============================================================================

@rt("/entities/search")
def get(q: str = ""):
    """Search and filter entities"""
    # Get all entities from JSON knowledge graph
    kg = load_knowledge_graph()
    entities = kg.get("entities", [])

    # Filter by search query if provided
    if q:
        q_lower = q.lower()
        entities = [
            e for e in entities
            if q_lower in e["name"].lower()
            or q_lower in e["value"].lower()
            or q_lower in e.get("description", "").lower()
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
    from entity_ui_components import EntityTypeGroup, ENTITY_TYPE_LABELS
    type_order = ["person", "date", "preference", "fact", "location", "relationship"]
    type_groups = []
    for entity_type in type_order:
        if entity_type in by_type:
            type_groups.append(EntityTypeGroup(entity_type, by_type[entity_type]))

    # Add any other types not in the standard order
    for entity_type in by_type:
        if entity_type not in type_order:
            type_groups.append(EntityTypeGroup(entity_type, by_type[entity_type]))

    # Return the entity content
    if type_groups:
        return type_groups
    else:
        return Div(
            Div("🔍", cls="text-4xl mb-2"),
            P(
                "No entities found" if q else "No entities yet",
                cls="text-sm text-muted-foreground"
            ),
            cls="flex flex-col items-center justify-center p-8 text-center"
        )


@rt("/entity/{entity_id}/edit-form")
def get(entity_id: int):
    """Get edit form for an entity"""
    # Load knowledge graph from JSON
    kg = load_knowledge_graph()

    # Find the entity by ID
    entity = None
    for e in kg.get("entities", []):
        if e["id"] == entity_id:
            entity = e
            break

    if not entity:
        return Div()

    return EntityEditForm(entity)


@rt("/entity/{entity_id}/cancel-edit")
def get(entity_id: int):
    """Cancel edit and restore original entity display"""
    # Load knowledge graph from JSON
    kg = load_knowledge_graph()

    # Find the entity by ID
    entity = None
    for e in kg.get("entities", []):
        if e["id"] == entity_id:
            entity = e
            break

    if not entity:
        return Div()

    return EntityListItem(entity)


@rt("/entity/{entity_id}/update")
def put(entity_id: int, request):
    """Update an entity in the knowledge graph JSON with support for type-specific attributes"""
    import asyncio

    # Get form data
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    form_data = loop.run_until_complete(request.form())
    loop.close()

    # Extract core fields
    name = form_data.get("name", "")
    value = form_data.get("value", "")
    description = form_data.get("description", "")
    confidence = float(form_data.get("confidence", 1.0))

    # Validate core inputs
    if not name or not value:
        return Div()

    # Load knowledge graph from JSON
    kg = load_knowledge_graph()

    # Find and update the entity
    entity = None
    for e in kg.get("entities", []):
        if e["id"] == entity_id:
            entity = e
            # Update core fields
            e["name"] = name
            e["value"] = value
            e["description"] = description
            e["confidence"] = confidence

            # Update type-specific attributes (prefixed with attr_)
            for field_name, field_value in form_data.items():
                if field_name.startswith("attr_"):
                    attr_name = field_name[5:]  # Remove "attr_" prefix

                    # Convert value to appropriate type based on existing value
                    if attr_name in e:
                        existing_value = e[attr_name]

                        # Boolean conversion
                        if isinstance(existing_value, bool):
                            e[attr_name] = field_value == "true"
                        # Numeric conversion
                        elif isinstance(existing_value, int):
                            try:
                                e[attr_name] = int(field_value) if field_value else 0
                            except ValueError:
                                e[attr_name] = field_value
                        elif isinstance(existing_value, float):
                            try:
                                e[attr_name] = float(field_value) if field_value else 0.0
                            except ValueError:
                                e[attr_name] = field_value
                        # List conversion (comma-separated)
                        elif isinstance(existing_value, list):
                            e[attr_name] = [item.strip() for item in field_value.split(",")] if field_value else []
                        # Default: string
                        else:
                            e[attr_name] = field_value
                    else:
                        # New attribute - store as-is (string)
                        e[attr_name] = field_value

            break

    if not entity:
        return Div()

    # Save updated knowledge graph
    if not save_knowledge_graph(kg):
        logger.error(f"Failed to save knowledge graph after updating entity {entity_id}")
        return Div()

    logger.info(f"Updated entity {entity_id}: {name}")

    # Return updated entity list item
    return EntityListItem(entity)


@rt("/entity/{entity_id}/delete")
def delete(entity_id: int):
    """Delete an entity from the knowledge graph JSON"""
    # Load knowledge graph from JSON
    kg = load_knowledge_graph()

    # Find and remove the entity
    entities = kg.get("entities", [])
    entity_found = False
    for i, e in enumerate(entities):
        if e["id"] == entity_id:
            entity_name = e["name"]
            entities.pop(i)
            entity_found = True
            break

    if not entity_found:
        return Div()

    # Remove any relationships that reference this entity
    relationships = kg.get("relationships", [])
    kg["relationships"] = [
        rel for rel in relationships
        if rel["entity1_id"] != entity_id and rel["entity2_id"] != entity_id
    ]

    # Save updated knowledge graph
    if not save_knowledge_graph(kg):
        logger.error(f"Failed to save knowledge graph after deleting entity {entity_id}")
        return Div()

    logger.info(f"Deleted entity {entity_id}: {entity_name}")

    # Return empty div (HTMX will remove the item)
    return Div()


# ============================================================================
# Sidebar Tab Routes
# ============================================================================

@rt("/sidebar/knowledge-graph")
def get():
    """Return Knowledge Graph sidebar content"""
    kg = load_knowledge_graph()
    entities = kg.get("entities", [])
    return EntitySidebar(entities)


@rt("/sidebar/learning-path")
def get():
    """Return Learning Path sidebar content"""
    active_objective = get_active_objective()
    return ObjectiveSidebar(active_objective)


# ============================================================================
# Learning Objectives Routes
# ============================================================================

@rt("/objective/create-from-chat")
async def post(topic: str, replace: bool = False):
    """Create new learning objective from chat message"""
    try:
        logger.info(f"Creating learning objective for topic: {topic}")

        # Decompose the objective using LLM
        objective = decompose_objective_with_llm(
            title=f"Learn {topic}",
            description=f"Master the fundamentals and advanced concepts of {topic}",
            client=client,
            parent_id=None,
            current_depth=0
        )

        # Set as active objective (archive existing if replace=True)
        set_active_objective(objective, archive_existing=replace)

        logger.info(f"Created learning objective: {objective['title']}")

        # Return the updated sidebar
        return ObjectiveSidebar(objective)

    except Exception as e:
        logger.error(f"Error creating learning objective: {e}")
        return Div(
            P(f"Error creating learning objective: {str(e)}", cls="text-error p-4"),
            cls="alert alert-error"
        )


@rt("/objective/clear")
def delete():
    """Clear the active learning objective"""
    try:
        clear_active_objective(archive=True)
        logger.info("Cleared active learning objective")
        return NoActiveObjectiveState()
    except Exception as e:
        logger.error(f"Error clearing objective: {e}")
        return Div(
            P(f"Error clearing objective: {str(e)}", cls="text-error"),
            cls="alert alert-error"
        )


@rt("/objective/{obj_id}/update-mastery")
def put(obj_id: int, level: str):
    """Update mastery level for an objective"""
    try:
        objectives = load_learning_objectives()
        active = objectives.get("active_objective")

        if not active:
            return Div()

        # Update mastery in the tree
        from learning_objectives_manager import update_mastery_by_id
        if update_mastery_by_id(active, obj_id, level):
            objectives["active_objective"] = active
            save_learning_objectives(objectives)
            logger.info(f"Updated mastery for objective {obj_id} to {level}")

        # Return updated tree
        return ObjectiveSidebar(active)

    except Exception as e:
        logger.error(f"Error updating mastery: {e}")
        return Div()


@rt("/objectives/refresh")
def get():
    """Refresh the objectives sidebar (for polling)"""
    active_objective = get_active_objective()
    return ObjectiveSidebar(active_objective)


if __name__ == "__main__":
    serve(port=config.SERVER_PORT)
