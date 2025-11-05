"""
PromptPane MUI Components

This module contains all MonsterUI component generation logic:
- MUI tag parser
- Component generators (buttons, sliders, checkboxes, rating, toggle, etc.)
- Optimistic UI JavaScript helpers
- MUI tag processing
"""

from fasthtml.common import *
from monsterui.all import *
from html.parser import HTMLParser
import re
import time

# ============================================================================
# MUI Tag Parser
# ============================================================================

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

# ============================================================================
# MUI Component Generators
# ============================================================================

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

# ============================================================================
# MUI Tag Processing
# ============================================================================

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
