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

class MUITagParser(HTMLParser):
    """Parse <mui> tags and extract their content"""
    def __init__(self):
        super().__init__()
        self.mui_tags = []
        self.current_tag = None
        self.tag_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'mui':
            attrs_dict = dict(attrs)
            self.current_tag = {
                'type': attrs_dict.get('type', 'buttons'),
                'attrs': attrs_dict,
                'options': [],
                'content': ''
            }
            self.tag_depth = 1
        elif self.current_tag and tag == 'option':
            attrs_dict = dict(attrs)
            self.current_tag['options'].append({
                'value': attrs_dict.get('value', ''),
                'label': '',
                'attrs': attrs_dict
            })

    def handle_endtag(self, tag):
        if tag == 'mui' and self.current_tag:
            self.tag_depth -= 1
            if self.tag_depth == 0:
                self.mui_tags.append(self.current_tag)
                self.current_tag = None

    def handle_data(self, data):
        if self.current_tag:
            # Add data to the last option if we have options
            if self.current_tag['options']:
                self.current_tag['options'][-1]['label'] += data.strip()

def parse_mui_tags(content):
    """Extract MUI tags from content and return tags and cleaned content"""
    parser = MUITagParser()
    parser.feed(content)
    return parser.mui_tags, content

def generate_mui_button_group(options, session_id):
    """Generate MonsterUI button group from options"""
    buttons = []
    for opt in options:
        label = opt['label'] or opt['value']
        # Create button that sends message via HTMX
        btn = Button(
            label,
            cls=ButtonT.primary + " mui-button",
            hx_post=f"/send-button/{session_id}",
            hx_vals=f'{{"message": "{opt["value"]}"}}',
            hx_target="#chat-messages",
            hx_swap="innerHTML"
        )
        buttons.append(btn)

    return DivLAligned(*buttons, cls="gap-2 flex-wrap my-2")

def generate_mui_card(options, content, session_id):
    """Generate MonsterUI card containing other components"""
    # Generate nested components if any
    inner_components = []
    if options:
        inner_components.append(generate_mui_button_group(options, session_id))

    return Card(
        *inner_components,
        cls="my-2"
    )

def generate_mui_component(tag_info, session_id):
    """Generate MonsterUI component from parsed tag"""
    component_type = tag_info['type']
    options = tag_info['options']
    content = tag_info['content']

    if component_type == 'buttons':
        return generate_mui_button_group(options, session_id)
    elif component_type == 'card':
        return generate_mui_card(options, content, session_id)
    else:
        # Unknown type, return empty div
        return Div()

def process_mui_tags(content, session_id):
    """Process MUI tags in content and return components + cleaned markdown"""
    # Find all MUI tags with regex to get positions
    mui_pattern = r'<mui[^>]*>.*?</mui>'
    matches = list(re.finditer(mui_pattern, content, re.DOTALL))

    if not matches:
        return [], content

    # Parse the tags
    mui_tags, _ = parse_mui_tags(content)

    # Build components and create placeholders (use HTML comments that markdown preserves)
    components = []
    result_content = content

    for i, (match, tag_info) in enumerate(zip(reversed(matches), reversed(mui_tags))):
        component = generate_mui_component(tag_info, session_id)
        components.insert(0, component)

        # Replace the MUI tag with an HTML comment placeholder
        placeholder = f"<!--MUI_COMPONENT_{i}-->"
        result_content = result_content[:match.start()] + placeholder + result_content[match.end():]

    return components, result_content

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

        # Render markdown with MonsterUI styling
        rendered_md = render_md(cleaned_content)

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

    # Chat messages container
    messages = Div(
        *[ChatMessage(msg["role"], msg["content"], msg.get("timestamp"), session_id)
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
        return [ChatMessage(msg["role"], msg["content"], msg.get("timestamp"), session_id)
                for msg in conversation]

    # Add user message
    add_message(session_id, "user", message)

    # Get conversation history for context
    conversation = get_conversation(session_id)

    # System prompt explaining MUI tags
    system_prompt = """CRITICAL: You MUST use <mui> tags for ALL multiple choice questions. Every question needs clickable buttons.

How to create buttons:
<mui type="buttons">
<option value="answer1">Label 1</option>
<option value="answer2">Label 2</option>
</mui>

MULTI-QUESTION QUIZ FORMAT - FOLLOW THIS EXACTLY:
Question 1: What is 2+2?
<mui type="buttons">
<option value="3">3</option>
<option value="4">4</option>
<option value="5">5</option>
<option value="6">6</option>
</mui>

Question 2: What is Python?
<mui type="buttons">
<option value="snake">A snake</option>
<option value="language">A programming language</option>
<option value="food">A food</option>
<option value="game">A game</option>
</mui>

Question 3: What does print() do?
<mui type="buttons">
<option value="prints">Prints to console</option>
<option value="saves">Saves a file</option>
<option value="deletes">Deletes data</option>
<option value="calculates">Calculates math</option>
</mui>

RULES:
1. EVERY question MUST have <mui> buttons immediately after the question text
2. NO question should be without buttons
3. When creating multiple questions, EACH ONE needs its own <mui> button group
4. Do NOT skip any questions - they ALL need buttons"""

    messages_for_api = [
        {"role": "system", "content": system_prompt},
        *[{"role": msg["role"], "content": msg["content"]} for msg in conversation]
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
    messages = [ChatMessage(msg["role"], msg["content"], msg.get("timestamp"), session_id)
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

@rt("/send-button/{session_id}")
async def post(session_id: str, message: str):
    """Handle button click - sends the button value as a message"""
    # Add user message (button value)
    add_message(session_id, "user", message)

    # Get conversation history
    conversation = get_conversation(session_id)

    # System prompt explaining MUI tags
    system_prompt = """CRITICAL: You MUST use <mui> tags for ALL multiple choice questions. Every question needs clickable buttons.

How to create buttons:
<mui type="buttons">
<option value="answer1">Label 1</option>
<option value="answer2">Label 2</option>
</mui>

MULTI-QUESTION QUIZ FORMAT - FOLLOW THIS EXACTLY:
Question 1: What is 2+2?
<mui type="buttons">
<option value="3">3</option>
<option value="4">4</option>
<option value="5">5</option>
<option value="6">6</option>
</mui>

Question 2: What is Python?
<mui type="buttons">
<option value="snake">A snake</option>
<option value="language">A programming language</option>
<option value="food">A food</option>
<option value="game">A game</option>
</mui>

Question 3: What does print() do?
<mui type="buttons">
<option value="prints">Prints to console</option>
<option value="saves">Saves a file</option>
<option value="deletes">Deletes data</option>
<option value="calculates">Calculates math</option>
</mui>

RULES:
1. EVERY question MUST have <mui> buttons immediately after the question text
2. NO question should be without buttons
3. When creating multiple questions, EACH ONE needs its own <mui> button group
4. Do NOT skip any questions - they ALL need buttons"""

    messages_for_api = [
        {"role": "system", "content": system_prompt},
        *[{"role": msg["role"], "content": msg["content"]} for msg in conversation]
    ]

    try:
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=messages_for_api,
            model="openai/gpt-oss-120b",
            temperature=0.7,
            max_tokens=1024,
            tools=[{"type":"browser_search"},{"type":"code_interpreter"}]
        )

        assistant_message = chat_completion.choices[0].message.content
        add_message(session_id, "assistant", assistant_message)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        add_message(session_id, "assistant", error_msg)

    # Return updated conversation with scroll anchor
    conversation = get_conversation(session_id)
    messages = [ChatMessage(msg["role"], msg["content"], msg.get("timestamp"), session_id)
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

if __name__ == "__main__":
    serve(port=5001)
