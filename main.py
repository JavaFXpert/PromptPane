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

def extract_citation_urls(chat_completion):
    """Extract URLs from browser_search tool results"""
    citation_urls = {}

    try:
        message = chat_completion.choices[0].message
        if hasattr(message, 'executed_tools') and message.executed_tools:
            for tool in message.executed_tools:
                if tool.type == 'browser_search' and hasattr(tool, 'search_results'):
                    if tool.search_results and hasattr(tool.search_results, 'results'):
                        for idx, result in enumerate(tool.search_results.results):
                            citation_urls[idx] = {
                                'url': result.url,
                                'title': result.title
                            }
    except Exception as e:
        print(f"Error extracting citation URLs: {e}")

    return citation_urls

def make_citations_clickable(content, citation_urls):
    """Replace citation markers with clickable links"""
    if not citation_urls:
        return content

    # Pattern matches: 【4†L716-L718】
    pattern = r'【(\d+)†([^】]+)】'

    def replace_citation(match):
        index = int(match.group(1))
        line_ref = match.group(2)
        citation_text = match.group(0)

        if index in citation_urls:
            url = citation_urls[index]['url']
            title = citation_urls[index]['title']

            # Extract source name from title (before the first dash or similar separator)
            source_name = title.split(' - ')[0].split(' | ')[0].strip()

            # If source name is too long, use domain instead
            if len(source_name) > 50:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                # Remove 'www.' prefix if present
                source_name = domain.replace('www.', '')

            # Create user-friendly clickable link
            friendly_citation = f'[{source_name}]'
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="citation-link" title="{title}">{friendly_citation}</a>'
        else:
            return citation_text

    return re.sub(pattern, replace_citation, content)

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

# ============================================================================
# Optimistic UI JavaScript Helpers - DRY principle for interactive components
# ============================================================================

def get_optimistic_ui_onclick(value_source='this.dataset.value'):
    """
    Generate onclick JavaScript for optimistic UI pattern.

    Security: Uses data attributes to avoid XSS vulnerabilities from string interpolation.

    Args:
        value_source: JavaScript expression to get the message value safely.
                     Default: 'this.dataset.value' (reads from data-value attribute)
                     Examples: "this.dataset.value", "document.getElementById('slider-1').value"

    Returns:
        String containing the complete onclick JavaScript handler
    """
    return f"""
        const msg = {value_source};
        const now = new Date().toLocaleTimeString('en-US', {{hour: 'numeric', minute: '2-digit', hour12: true}});

        // Create user message with safe HTML escaping
        const userMsgDiv = document.createElement('div');
        userMsgDiv.className = 'mb-4';
        userMsgDiv.innerHTML = `
            <div class="flex gap-3 justify-end">
                <div class="space-y-1">
                    <div class="rounded-lg p-4 max-w-2xl bg-primary text-primary-foreground"></div>
                    <small class="text-muted-foreground mt-1">${{now}}</small>
                </div>
            </div>
        `;
        // Safely set text content (prevents XSS)
        userMsgDiv.querySelector('.rounded-lg').textContent = msg;
        document.getElementById('scroll-anchor').insertAdjacentElement('beforebegin', userMsgDiv);

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
        setTimeout(() => {{
            const anchor = document.getElementById('scroll-anchor');
            if (anchor) anchor.scrollIntoView({{ behavior: 'smooth', block: 'end' }});
        }}, 100);
    """

def get_optimistic_ui_after_swap():
    """
    Generate hx_on__after_swap JavaScript for cleanup after HTMX swap.

    Returns:
        String containing the complete after_swap JavaScript handler
    """
    return """
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) loadingIndicator.remove();
        if (typeof renderMathInElement !== 'undefined') {
            try {
                renderMathInElement(document.getElementById('chat-messages'), {
                    delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}, {left: '\\\\[', right: '\\\\]', display: true}, {left: '\\\\(', right: '\\\\)', display: false}],
                    throwOnError: false
                });
            } catch(e) {}
        }
        setTimeout(() => {
            const anchor = document.getElementById('scroll-anchor');
            if (anchor) anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
            const mainInput = document.getElementById('message-input');
            if (mainInput) mainInput.focus();
        }, 100);
    """

def generate_mui_button_group(options, session_id):
    """Generate MonsterUI button group from options"""
    buttons = []
    for opt in options:
        label = opt['label'] or opt['value']
        value = opt['value']
        # Create button that sends message via HTMX with optimistic UI
        # Security: Use data-value attribute to safely store value (prevents XSS)
        btn = Button(
            label,
            cls=ButtonT.primary + " mui-button",
            hx_post=f"/send-button/{session_id}",
            hx_vals=f'{{"message": "{value}"}}',
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            onclick=get_optimistic_ui_onclick(),  # Uses default this.dataset.value
            data_value=value  # FastHTML properly escapes this attribute
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

def generate_mui_slider(tag_info, session_id):
    """Generate MonsterUI slider component"""
    attrs = tag_info['attrs']
    min_val = int(attrs.get('min', '0'))
    max_val = int(attrs.get('max', '100'))
    step = int(attrs.get('step', '1'))
    default_val = int(attrs.get('value', str((min_val + max_val) // 2)))
    label = attrs.get('label', '')

    # Generate unique ID for this slider
    slider_id = f"slider-{abs(hash(str(tag_info)))}"

    # Calculate tick marks (show at intervals)
    range_size = max_val - min_val
    tick_interval = max(1, range_size // 10)  # Show ~10 ticks
    ticks = list(range(min_val, max_val + 1, tick_interval))

    # Create datalist for tick marks
    datalist_id = f"{slider_id}-ticks"
    tick_options = [Option(value=str(tick)) for tick in ticks]
    datalist = Datalist(*tick_options, id=datalist_id)

    return Div(
        # Label
        Label(label, cls="font-semibold mb-2") if label else None,

        # Slider with end labels
        Div(
            # Min label
            Span(str(min_val), cls="text-sm text-muted-foreground"),

            # Slider itself
            Div(
                Input(
                    type="range",
                    id=slider_id,
                    min=str(min_val),
                    max=str(max_val),
                    step=str(step),
                    value=str(default_val),
                    list=datalist_id,
                    oninput=f"document.getElementById('{slider_id}-value').textContent = this.value",
                    cls="w-full"
                ),
                datalist,
                cls="flex-1 px-4"
            ),

            # Max label
            Span(str(max_val), cls="text-sm text-muted-foreground"),

            cls="flex items-center gap-2 mb-3"
        ),

        # Current value display
        Div(
            Span("Selected value: ", cls=TextT.muted),
            Span(str(default_val), id=f"{slider_id}-value", cls="font-bold text-lg"),
            cls="text-center mb-3"
        ),

        # Submit button
        Button(
            "Submit Answer",
            cls=ButtonT.primary,
            hx_post=f"/send-button/{session_id}",
            hx_vals=f"js:{{message: document.getElementById('{slider_id}').value}}",
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            # Value read from DOM element (safe - no user input interpolation)
            onclick=get_optimistic_ui_onclick(value_source=f"document.getElementById('{slider_id}').value")
        ),

        cls="space-y-2 my-4 p-4 border border-border rounded-lg"
    )

def generate_mui_checkboxes(tag_info, session_id):
    """Generate MonsterUI checkbox group component"""
    options = tag_info['options']
    attrs = tag_info['attrs']
    label = attrs.get('label', '')

    # Generate unique ID for this checkbox group
    group_id = f"checkbox-group-{abs(hash(str(tag_info)))}"

    checkbox_items = []
    for i, opt in enumerate(options):
        checkbox_id = f"{group_id}-{i}"
        opt_label = opt['label'] or opt['value']

        checkbox_items.append(
            Div(
                Input(
                    type="checkbox",
                    id=checkbox_id,
                    value=opt['value'],
                    name=group_id,
                    cls="checkbox checkbox-primary w-5 h-5 cursor-pointer"
                ),
                Label(opt_label, **{"for": checkbox_id}, cls="cursor-pointer ml-2"),
                cls="flex items-center gap-2 p-2 hover:bg-muted rounded"
            )
        )

    return Div(
        # Label
        Label(label, cls="font-semibold mb-3") if label else None,

        # Checkboxes
        Div(*checkbox_items, cls="space-y-2 mb-4"),

        # Submit button
        Button(
            "Submit Answers",
            cls=ButtonT.primary,
            hx_post=f"/send-button/{session_id}",
            hx_vals=f"""js:{{
                message: Array.from(document.querySelectorAll('input[name="{group_id}"]:checked'))
                    .map(cb => cb.value)
                    .join(', ') || 'none selected'
            }}""",
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            # Value read from checked checkboxes (safe - values come from controlled options)
            onclick=get_optimistic_ui_onclick(
                value_source=f"Array.from(document.querySelectorAll('input[name=\"{group_id}\"]:checked')).map(cb => cb.value).join(', ') || 'none selected'"
            )
        ),

        cls="space-y-2 my-4 p-4 border border-border rounded-lg"
    )

def generate_mui_rating(tag_info, session_id):
    """Generate MonsterUI star rating component"""
    attrs = tag_info['attrs']
    label = attrs.get('label', '')
    max_rating = int(attrs.get('max', '5'))

    # Generate unique ID for this rating
    import time
    rating_id = f"rating-{int(time.time() * 1000000)}"

    # Create star radio buttons in normal order (1 to max)
    stars = []

    # Add hidden 0-star option as default
    stars.append(
        Input(
            type="radio",
            name=rating_id,
            value="0",
            checked=True,
            cls="rating-hidden",
            id=f"{rating_id}-0"
        )
    )

    for i in range(1, max_rating + 1):
        stars.append(
            Input(
                type="radio",
                name=rating_id,
                value=str(i),
                cls="mask mask-star-2 bg-orange-400",
                id=f"{rating_id}-{i}"
            )
        )

    return Div(
        # Label
        Label(label, cls="font-semibold mb-2") if label else None,

        # Rating stars
        Div(
            *stars,
            cls="rating rating-lg mb-3"
        ),

        # Submit button
        Button(
            "Submit Rating",
            cls=ButtonT.primary,
            hx_post=f"/send-button/{session_id}",
            hx_vals=f"""js:{{
                message: document.querySelector('input[name="{rating_id}"]:checked')?.value || '0'
            }}""",
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            # Value is numeric rating from radio buttons (safe - controlled values)
            onclick=get_optimistic_ui_onclick(
                value_source=f"document.querySelector('input[name=\"{rating_id}\"]:checked')?.value || '0'"
            )
        ),

        cls="space-y-2 my-4 p-4 border border-border rounded-lg"
    )

def generate_mui_toggle(tag_info, session_id):
    """Generate MonsterUI toggle switch component"""
    attrs = tag_info['attrs']
    label = attrs.get('label', '')
    default_checked = attrs.get('checked', 'false').lower() == 'true'

    # Generate unique ID for this toggle
    import time
    toggle_id = f"toggle-{int(time.time() * 1000000)}"

    return Div(
        # Label
        Label(label, cls="font-semibold mb-2") if label else None,

        # Toggle switch
        Label(
            Input(
                type="checkbox",
                id=toggle_id,
                cls="toggle toggle-primary",
                checked=default_checked
            ),
            cls="cursor-pointer mb-3 flex items-center"
        ),

        # Submit button
        Button(
            "Submit Answer",
            cls=ButtonT.primary,
            hx_post=f"/send-button/{session_id}",
            hx_vals=f"""js:{{message: document.getElementById('{toggle_id}').checked ? 'yes' : 'no'}}""",
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            # Value is yes/no from toggle state (safe - controlled values)
            onclick=get_optimistic_ui_onclick(
                value_source=f"document.getElementById('{toggle_id}').checked ? 'yes' : 'no'"
            )
        ),

        cls="space-y-2 my-4 p-4 border border-border rounded-lg"
    )

def generate_mui_image(tag_info, session_id):
    """Generate MonsterUI image display component"""
    attrs = tag_info['attrs']
    src = attrs.get('src', '')
    caption = attrs.get('caption', '')
    alt = attrs.get('alt', caption or 'Image')

    if not src:
        return Div("Error: No image source provided", cls="text-error")

    image_components = []

    # Image with responsive styling
    image_components.append(
        Img(
            src=src,
            alt=alt,
            cls="max-w-full h-auto rounded-lg"
        )
    )

    # Optional caption
    if caption:
        image_components.append(
            P(caption, cls="text-sm text-muted-foreground text-center mt-2")
        )

    return Div(
        *image_components,
        cls="my-4 p-4 border border-border rounded-lg"
    )

def generate_mui_video(tag_info, session_id):
    """Generate MonsterUI YouTube video embed component"""
    attrs = tag_info['attrs']
    url = attrs.get('url', '')
    caption = attrs.get('caption', '')

    if not url:
        return Div("Error: No video URL provided", cls="text-error")

    # Extract YouTube video ID from various URL formats
    video_id = None
    import re

    # Match youtube.com/watch?v=VIDEO_ID
    match = re.search(r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    if match:
        video_id = match.group(1)

    if not video_id:
        return Div("Error: Invalid YouTube URL", cls="text-error")

    embed_url = f"https://www.youtube.com/embed/{video_id}"

    video_components = []

    # Responsive iframe container
    video_components.append(
        Div(
            Iframe(
                src=embed_url,
                width="560",
                height="315",
                frameborder="0",
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
                allowfullscreen=True,
                cls="w-full aspect-video rounded-lg"
            ),
            cls="relative w-full"
        )
    )

    # Optional caption
    if caption:
        video_components.append(
            P(caption, cls="text-sm text-muted-foreground text-center mt-2")
        )

    return Div(
        *video_components,
        cls="my-4 p-4 border border-border rounded-lg"
    )

def generate_mui_date(tag_info, session_id):
    """Generate MonsterUI date picker component"""
    attrs = tag_info['attrs']
    label = attrs.get('label', '')
    min_date = attrs.get('min', '')
    max_date = attrs.get('max', '')
    default_date = attrs.get('value', '')

    # Generate unique ID for this date picker
    import time
    date_id = f"date-{int(time.time() * 1000000)}"

    # Build input attributes
    input_attrs = {
        'type': 'date',
        'id': date_id,
        'cls': 'input input-bordered w-full mb-3'
    }

    if min_date:
        input_attrs['min'] = min_date
    if max_date:
        input_attrs['max'] = max_date
    if default_date:
        input_attrs['value'] = default_date

    return Div(
        # Label
        Label(label, cls="font-semibold mb-2") if label else None,

        # Date input
        Input(**input_attrs),

        # Submit button
        Button(
            "Submit Date",
            cls=ButtonT.primary,
            hx_post=f"/send-button/{session_id}",
            hx_vals=f"js:{{message: document.getElementById('{date_id}').value || 'no date selected'}}",
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            # Value from date input (safe - browser-controlled format)
            onclick=get_optimistic_ui_onclick(
                value_source=f"document.getElementById('{date_id}').value || 'no date selected'"
            )
        ),

        cls="space-y-2 my-4 p-4 border border-border rounded-lg"
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
    elif component_type == 'slider':
        return generate_mui_slider(tag_info, session_id)
    elif component_type == 'checkboxes':
        return generate_mui_checkboxes(tag_info, session_id)
    elif component_type == 'rating':
        return generate_mui_rating(tag_info, session_id)
    elif component_type == 'toggle':
        return generate_mui_toggle(tag_info, session_id)
    elif component_type == 'image':
        return generate_mui_image(tag_info, session_id)
    elif component_type == 'video':
        return generate_mui_video(tag_info, session_id)
    elif component_type == 'date':
        return generate_mui_date(tag_info, session_id)
    else:
        # Unknown type, return empty div
        return Div()

def extract_latex(content):
    """Extract LaTeX blocks and replace with placeholders"""
    import re

    latex_blocks = []

    # Extract \[...\] display math (with possible \begin{aligned})
    def save_bracket_display(match):
        latex_blocks.append(('display', match.group(0)))
        return f'<!--LATEX_BLOCK_{len(latex_blocks)-1}-->'

    content = re.sub(r'\\\[.*?\\\]', save_bracket_display, content, flags=re.DOTALL)

    # Extract $$...$$ display math
    def save_dollar_display(match):
        latex_blocks.append(('display', match.group(0)))
        return f'<!--LATEX_BLOCK_{len(latex_blocks)-1}-->'

    content = re.sub(r'\$\$(.*?)\$\$', save_dollar_display, content, flags=re.DOTALL)

    # Extract \(...\) inline math
    def save_paren_inline(match):
        latex_blocks.append(('inline', match.group(0)))
        return f'<!--LATEX_BLOCK_{len(latex_blocks)-1}-->'

    content = re.sub(r'\\\(.*?\\\)', save_paren_inline, content, flags=re.DOTALL)

    # Extract $...$ inline math (but not $$)
    def save_dollar_inline(match):
        latex_blocks.append(('inline', match.group(0)))
        return f'<!--LATEX_BLOCK_{len(latex_blocks)-1}-->'

    content = re.sub(r'(?<!\$)\$(?!\$)([^\$]+?)\$(?!\$)', save_dollar_inline, content)

    return content, latex_blocks

def restore_latex(content, latex_blocks):
    """Restore LaTeX blocks from placeholders - leave raw for KaTeX"""
    for i, (math_type, latex_content) in enumerate(latex_blocks):
        placeholder = f'<!--LATEX_BLOCK_{i}-->'
        # Restore LaTeX as-is, KaTeX will process it
        content = content.replace(placeholder, latex_content)

    return content

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
