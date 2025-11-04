"""PromptPane - A chatbot with dynamically generated UI controls using MonsterUI and Groq"""

from fasthtml.common import *
from monsterui.all import *
import os
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Create FastHTML app with MonsterUI theme
app, rt = fast_app(
    hdrs=Theme.blue.headers(highlightjs=True),
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

def ChatMessage(role, content, timestamp=None):
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
        # Render markdown with MonsterUI styling
        rendered_md = render_md(content)
        message_body = Div(Safe(rendered_md), cls=f"rounded-lg p-4 max-w-2xl {message_cls}")

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

    # Chat messages container
    messages = Div(
        *[ChatMessage(msg["role"], msg["content"], msg.get("timestamp"))
          for msg in conversation],
        Div(id="scroll-anchor"),
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
                type="submit"
            ),
            cls="gap-2 w-full"
        ),
        id="chat-form",
        hx_post=f"/chat/{session_id}",
        hx_target="#chat-messages",
        hx_swap="innerHTML",
        onsubmit="setTimeout(() => this.reset(), 10); return true;",
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
        return [ChatMessage(msg["role"], msg["content"], msg.get("timestamp"))
                for msg in conversation]

    # Add user message
    add_message(session_id, "user", message)

    # Get conversation history for context
    conversation = get_conversation(session_id)
    messages_for_api = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation
    ]

    try:
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=messages_for_api,
            model="openai/gpt-oss-120b",  # or "mixtral-8x7b-32768"
            temperature=0.7,
            max_tokens=1024,
            tools=[{"type":"browser_search"},{"type":"code_interpreter"}]
        )

        assistant_message = chat_completion.choices[0].message.content

        # Add assistant response
        add_message(session_id, "assistant", assistant_message)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        add_message(session_id, "assistant", error_msg)

    # Return updated conversation with scroll anchor
    conversation = get_conversation(session_id)
    messages = [ChatMessage(msg["role"], msg["content"], msg.get("timestamp"))
                for msg in conversation]

    # Add a scroll anchor at the bottom
    scroll_anchor = Div(id="scroll-anchor")
    scroll_script = Script("""
        setTimeout(() => {
            const anchor = document.getElementById('scroll-anchor');
            if (anchor) {
                anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        }, 100);
    """)

    return messages + [scroll_anchor, scroll_script]

@rt("/clear/{session_id}")
def post(session_id: str):
    """Clear conversation history"""
    if session_id in conversations:
        conversations[session_id] = []
    return Div(
        Div(
            DivCentered(
                UkIcon("message-circle", height=48, width=48, cls=TextT.muted),
                cls="mb-4"
            ),
            H4("No messages yet", cls=TextT.center),
            P("Start a conversation by typing a message below.",
              cls=(TextT.muted, TextT.center)),
            cls="space-y-2"
        ),
        cls="flex items-center justify-center h-full"
    )

if __name__ == "__main__":
    serve(port=5001)
