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
from typing import Any
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
        self.in_option = False
        self.capture_raw = False  # Flag to capture raw HTML content

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
            self.capture_raw = True  # Start capturing raw content
        elif self.current_tag and tag == 'option':
            attrs_dict = dict(attrs)
            self.current_tag['options'].append({
                'value': attrs_dict.get('value', ''),
                'label': '',
                'attrs': attrs_dict
            })
            self.in_option = True
        elif self.current_tag and self.capture_raw:
            # Capture raw HTML tags (like <tab>, <row>, etc.)
            attrs_str = ' '.join([f'{k}="{v}"' for k, v in attrs])
            tag_html = f'<{tag} {attrs_str}>' if attrs_str else f'<{tag}>'
            self.current_tag['content'] += tag_html

    def handle_endtag(self, tag):
        if tag == 'mui' and self.current_tag:
            self.tag_depth -= 1
            if self.tag_depth == 0:
                self.mui_tags.append(self.current_tag)
                self.current_tag = None
                self.capture_raw = False
        elif self.current_tag and tag == 'option':
            self.in_option = False
        elif self.current_tag and self.capture_raw and tag != 'mui':
            # Capture closing tags
            self.current_tag['content'] += f'</{tag}>'

    def handle_data(self, data):
        if self.current_tag:
            # Add data to the last option if we're inside an option tag
            if self.in_option and self.current_tag['options']:
                self.current_tag['options'][-1]['label'] += data.strip()
            # Also capture all raw content for components like tabs, grid, table
            elif self.capture_raw and not self.in_option:
                self.current_tag['content'] += data

def parse_mui_tags(content: str) -> tuple[list[dict[str, Any]], str]:
    """Extract MUI tags from content and return tags and cleaned content"""
    parser = MUITagParser()
    parser.feed(content)
    return parser.mui_tags, content

# ============================================================================
# Concept Link Extraction & Restoration
# ============================================================================

def extract_concept_tags(content: str, session_id: str) -> tuple[str, list[Any]]:
    """
    Extract <concept>term</concept> tags and replace with placeholders.
    Returns FastHTML Span components instead of HTML strings.

    This must be done BEFORE markdown rendering to preserve the tags.
    Similar pattern to MUI component extraction.

    Args:
        content: Markdown content with concept tags
        session_id: Current session ID for HTMX target

    Returns:
        Tuple of (content with placeholders, list of FastHTML Span elements)
    """
    from fasthtml.common import Span

    concept_components = []

    def replace_concept(match):
        term = match.group(1).strip()
        idx = len(concept_components)

        # Create FastHTML Span element (like MUI buttons do)
        # This ensures proper JavaScript attribute handling by FastHTML
        concept_span = Span(
            term,
            cls="concept-link",
            data_value=term,
            data_concept=term,
            hx_post=f"/explain-concept/{session_id}",
            hx_vals=f'{{"concept": "{term}"}}',
            hx_target="#scroll-anchor",
            hx_swap="beforebegin",
            hx_on__after_swap=get_optimistic_ui_after_swap(),
            onclick=get_optimistic_ui_onclick('this.dataset.value')
        )

        concept_components.append(concept_span)
        return f'<!--CONCEPT_{idx}-->'

    # Extract <concept>...</concept> tags
    pattern = r'<concept>(.*?)</concept>'
    content = re.sub(pattern, replace_concept, content, flags=re.DOTALL)

    return content, concept_components

# ============================================================================
# Optimistic UI JavaScript Helpers - DRY principle for interactive components
# ============================================================================

def get_optimistic_ui_onclick(value_source: str = 'this.dataset.value') -> str:
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

def get_optimistic_ui_after_swap() -> str:
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
    """Generate MonsterUI checkbox group component using native CheckboxX"""
    options = tag_info['options']
    attrs = tag_info['attrs']
    label = attrs.get('label', '')

    # Generate unique ID for this checkbox group
    group_id = f"checkbox-group-{abs(hash(str(tag_info)))}"

    checkbox_items = []
    for i, opt in enumerate(options):
        checkbox_id = f"{group_id}-{i}"
        opt_label = opt['label'] or opt['value']

        # Create explicit checkbox input with DaisyUI styling
        checkbox_items.append(
            Div(
                Label(
                    Input(
                        type="checkbox",
                        id=checkbox_id,
                        value=opt['value'],
                        name=group_id,
                        cls="checkbox checkbox-primary"
                    ),
                    Span(opt_label, cls="ml-2"),
                    cls="flex items-center cursor-pointer"
                ),
                cls="p-2 hover:bg-muted rounded"
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
    """Generate MonsterUI toggle switch component using native Switch"""
    attrs = tag_info['attrs']
    label = attrs.get('label', '')
    default_checked = attrs.get('checked', 'false').lower() == 'true'

    # Generate unique ID for this toggle
    toggle_id = f"toggle-{int(time.time() * 1000000)}"

    # Build switch with explicit input control using DaisyUI toggle classes
    switch_input = Input(
        type="checkbox",
        id=toggle_id,
        checked=default_checked,
        cls="toggle toggle-primary"
    )

    return Div(
        # Label and toggle switch
        Div(
            Label(label, cls="font-semibold") if label else None,
            switch_input,
            cls="flex items-center gap-3 mb-3"
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

def generate_mui_grid(tag_info, session_id):
    """Generate MonsterUI grid layout component using native Grid"""
    attrs = tag_info['attrs']
    cols = int(attrs.get('cols', '2'))
    gap = attrs.get('gap', '4')

    # Support responsive columns
    cols_sm = int(attrs.get('cols_sm')) if attrs.get('cols_sm') else None
    cols_md = int(attrs.get('cols_md')) if attrs.get('cols_md') else None
    cols_lg = int(attrs.get('cols_lg')) if attrs.get('cols_lg') else None
    cols_xl = int(attrs.get('cols_xl')) if attrs.get('cols_xl') else None

    content = tag_info['content'].strip()

    if not content:
        return Div("Error: Grid must have content", cls="text-error")

    # Parse rows from content (each <row> tag becomes a grid item)
    row_pattern = r'<row>(.*?)</row>'
    rows = re.findall(row_pattern, content, re.DOTALL)

    if not rows:
        # If no <row> tags, just split by newlines
        rows = [line.strip() for line in content.split('\n') if line.strip()]

    # Process concept tags and render markdown in each grid item
    grid_items = []
    for row in rows:
        row_text = row.strip()

        # Extract concept tags first
        concept_extracted, concept_components = extract_concept_tags(row_text, session_id)

        # Check if content has markdown indicators
        has_markdown = any(indicator in concept_extracted for indicator in ['**', '*', '#', '`', '[', '-', '1.', '!'])

        if has_markdown:
            # Render as markdown
            rendered_md = render_md(concept_extracted)
        else:
            # Plain text
            rendered_md = concept_extracted

        # Replace concept placeholders with actual components
        row_parts = []
        remaining = rendered_md
        for idx, component in enumerate(concept_components):
            placeholder = f'<!--CONCEPT_{idx}-->'
            if placeholder in remaining:
                before, remaining = remaining.split(placeholder, 1)
                if before.strip():
                    row_parts.append(Safe(before))
                row_parts.append(component)

        # Add any remaining content
        if remaining.strip():
            row_parts.append(Safe(remaining))

        # If no components, just show rendered content
        if not row_parts:
            row_parts = [Safe(rendered_md)]

        grid_items.append(Div(*row_parts, cls="p-4 border border-border rounded-lg"))

    # Use native MonsterUI Grid component with responsive columns
    return Div(
        Grid(
            *grid_items,
            cols=cols,
            cols_sm=cols_sm,
            cols_md=cols_md,
            cols_lg=cols_lg,
            cols_xl=cols_xl,
            cls=f"gap-{gap}"
        ),
        cls="my-4"
    )

def generate_mui_stat(tag_info, session_id):
    """Generate MonsterUI stat/metric display component"""
    attrs = tag_info['attrs']
    label = attrs.get('label', '')
    value = attrs.get('value', '')
    desc = attrs.get('desc', attrs.get('change', ''))  # Support both 'desc' and 'change'

    if not label or not value:
        return Div("Error: Stat requires label and value attributes", cls="text-error")

    stat_content = [
        Div(label, cls="stat-title"),
        Div(value, cls="stat-value")
    ]

    if desc:
        stat_content.append(Div(desc, cls="stat-desc"))

    return Div(
        Div(*stat_content, cls="stat"),
        cls="stats shadow my-4"
    )

def generate_mui_table(tag_info, session_id):
    """Generate MonsterUI table component"""
    attrs = tag_info['attrs']
    headers_str = attrs.get('headers', '')
    content = tag_info['content'].strip()

    if not headers_str:
        return Div("Error: Table requires headers attribute", cls="text-error")

    # Parse headers
    headers = [h.strip() for h in headers_str.split(',')]

    # Parse rows from content
    row_pattern = r'<row>(.*?)</row>'
    rows_data = re.findall(row_pattern, content, re.DOTALL)

    if not rows_data:
        # Fallback: split by newlines
        rows_data = [line.strip() for line in content.split('\n') if line.strip()]

    # Build table rows
    table_rows = []
    for row_str in rows_data:
        # Split row by comma (or pipe if present)
        if '|' in row_str:
            cells = [cell.strip() for cell in row_str.split('|')]
        else:
            cells = [cell.strip() for cell in row_str.split(',')]

        # Process concept tags in each cell
        processed_cells = []
        for cell in cells:
            concept_extracted, concept_components = extract_concept_tags(cell, session_id)

            # If cell has concept tags, build content parts
            if concept_components:
                cell_parts = []
                remaining = concept_extracted
                for idx, component in enumerate(concept_components):
                    placeholder = f'<!--CONCEPT_{idx}-->'
                    if placeholder in remaining:
                        before, remaining = remaining.split(placeholder, 1)
                        if before.strip():
                            cell_parts.append(before)
                        cell_parts.append(component)

                # Add remaining text
                if remaining.strip():
                    cell_parts.append(remaining)

                processed_cells.append(Td(*cell_parts))
            else:
                # No concepts, just plain text
                processed_cells.append(Td(cell))

        table_rows.append(Tr(*processed_cells))

    # Use MonsterUI TableT styling instead of DaisyUI classes
    return Div(
        Table(
            Thead(Tr(*[Th(h) for h in headers])),
            Tbody(*table_rows),
            cls=(TableT.striped, TableT.hover, TableT.divider)
        ),
        cls="my-4"
    )

def generate_mui_tabs(tag_info, session_id):
    """Generate MonsterUI tabs component"""
    content = tag_info['content'].strip()

    # Debug logging
    print(f"[DEBUG] Tabs content received: {content[:500]}...")

    # Parse tab items from content - handle both straight and curly quotes
    # Pattern matches: label="..." or label="..." or label='...' or label='...'
    tab_pattern = r'<tab\s+label=["\u201c\u201d\'](.*?)["\u201c\u201d\']>(.*?)</tab>'
    tabs = re.findall(tab_pattern, content, re.DOTALL)

    print(f"[DEBUG] Found {len(tabs)} tabs")
    for i, (label, _) in enumerate(tabs):
        print(f"[DEBUG] Tab {i}: {label}")

    if not tabs:
        error_msg = f"Error: Tabs must contain <tab label=\"...\">content</tab> items. Received content: {content[:100]}"
        print(f"[ERROR] {error_msg}")
        return Div(
            P("Tab parsing failed!", cls="text-error font-bold"),
            P(f"Expected format: <tab label=\"Label\">Content</tab>", cls="text-sm"),
            P(f"Received: {content[:200]}...", cls="text-sm text-muted-foreground"),
            cls="p-4 border border-error rounded-lg my-4"
        )

    tab_id = f"tabs-{int(time.time() * 1000000)}"

    # Build tab buttons and content
    tab_buttons = []
    tab_contents = []

    for i, (label, tab_content) in enumerate(tabs):
        is_first = (i == 0)

        # Button for each tab with enhanced contrast
        if is_first:
            # Active tab: bold text, light blue background, rounded corners
            active_cls = "tab-active font-bold bg-blue-200 text-blue-900 border-b-4 border-blue-400 rounded-t-lg"
        else:
            # Inactive tab: lighter styling with rounded corners
            active_cls = "text-muted-foreground hover:bg-blue-50 rounded-t-lg"

        tab_buttons.append(
            Button(
                label,
                type="button",
                role="tab",
                cls=f"tab {active_cls}",
                data_tab_index=str(i),
                data_tab_container=tab_id,
                onclick=f"""
                    console.log('Tab clicked: {label}', 'index: {i}');
                    // Update all tabs in this container
                    document.querySelectorAll('[data-tab-container="{tab_id}"]').forEach(tab => {{
                        // Remove active styles
                        tab.classList.remove('tab-active', 'font-bold', 'bg-blue-200', 'text-blue-900', 'border-b-4', 'border-blue-400');
                        // Add inactive styles
                        tab.classList.add('text-muted-foreground', 'hover:bg-blue-50');
                    }});
                    // Remove inactive styles from clicked tab
                    this.classList.remove('text-muted-foreground', 'hover:bg-blue-50');
                    // Add active styles to clicked tab
                    this.classList.add('tab-active', 'font-bold', 'bg-blue-200', 'text-blue-900', 'border-b-4', 'border-blue-400');

                    // Hide all tab contents
                    document.querySelectorAll('[id^="{tab_id}-content-"]').forEach(content => {{
                        content.style.display = 'none';
                    }});
                    // Show selected tab content
                    const targetContent = document.getElementById('{tab_id}-content-{i}');
                    if (targetContent) {{
                        targetContent.style.display = 'block';
                        console.log('Showing content for tab {i}');
                    }} else {{
                        console.error('Content element not found:', '{tab_id}-content-{i}');
                    }}
                """
            )
        )

        # Tab content panel - extract concepts first, then render
        content_text = tab_content.strip()

        # Extract concept tags from tab content
        concept_extracted, concept_components = extract_concept_tags(content_text, session_id)

        # Simple check: if content has markdown indicators, render it
        has_markdown = any(indicator in concept_extracted for indicator in ['**', '*', '#', '`', '[', '-', '1.'])

        if has_markdown:
            # Render as markdown using MonsterUI's render_md
            rendered_md = render_md(concept_extracted)
        else:
            # Plain text
            rendered_md = concept_extracted

        # Replace concept placeholders with actual components
        content_parts = []
        remaining = rendered_md
        for idx, component in enumerate(concept_components):
            placeholder = f'<!--CONCEPT_{idx}-->'
            if placeholder in remaining:
                before, remaining = remaining.split(placeholder, 1)
                if before.strip():
                    content_parts.append(Safe(before))
                content_parts.append(component)

        # Add any remaining content
        if remaining.strip():
            content_parts.append(Safe(remaining))

        # If no components, just show rendered content
        if not content_parts:
            content_parts = [Safe(rendered_md)]

        display_style = "block" if is_first else "none"
        tab_contents.append(
            Div(
                *content_parts,
                id=f"{tab_id}-content-{i}",
                cls="p-4 border border-border rounded-b-lg bg-base-100",
                style=f"display:{display_style};"
            )
        )

    print(f"[DEBUG] Generated {len(tab_buttons)} tab buttons and {len(tab_contents)} content panels")

    return Div(
        # Tab buttons container with enhanced background contrast
        Div(
            *tab_buttons,
            role="tablist",
            cls="tabs tabs-bordered bg-base-200 p-2 rounded-t-lg shadow-sm"
        ),
        # Tab contents container
        Div(*tab_contents, cls="tab-content-container"),
        cls="my-4 border-2 border-base-300 rounded-lg shadow-md bg-base-100"
    )

def generate_mui_accordion(tag_info, session_id):
    """Generate MonsterUI accordion component using Accordion and AccordionItem"""
    content = tag_info['content'].strip()

    # Debug logging
    print(f"[DEBUG] Accordion content received: {content[:500]}...")

    # Parse accordion items from content - handle both straight and curly quotes
    # Pattern matches: title="..." or title="..."
    item_pattern = r'<item\s+title=["\u201c\u201d\'](.*?)["\u201c\u201d\']>(.*?)</item>'
    items = re.findall(item_pattern, content, re.DOTALL)

    print(f"[DEBUG] Found {len(items)} accordion items")
    for i, (title, _) in enumerate(items):
        print(f"[DEBUG] Item {i}: {title}")

    if not items:
        error_msg = f"Error: Accordion must contain <item title=\"...\">content</item> items. Received content: {content[:100]}"
        print(f"[ERROR] {error_msg}")
        return Div(
            P("Accordion parsing failed!", cls="text-error font-bold"),
            P(f"Expected format: <item title=\"Title\">Content</item>", cls="text-sm"),
            P(f"Received: {content[:200]}...", cls="text-sm text-muted-foreground"),
            cls="p-4 border border-error rounded-lg my-4"
        )

    # Build accordion items using MonsterUI's AccordionItem
    accordion_items = []

    for i, (title, item_content) in enumerate(items):
        is_first = (i == 0)

        # Extract concept tags from item content
        content_text = item_content.strip()
        concept_extracted, concept_components = extract_concept_tags(content_text, session_id)

        # Check if content has markdown indicators
        has_markdown = any(indicator in concept_extracted for indicator in ['**', '*', '#', '`', '[', '-', '1.'])

        if has_markdown:
            # Render as markdown
            rendered_md = render_md(concept_extracted)
        else:
            # Plain text
            rendered_md = concept_extracted

        # Replace concept placeholders with actual components
        content_parts = []
        remaining = rendered_md
        for idx, component in enumerate(concept_components):
            placeholder = f'<!--CONCEPT_{idx}-->'
            if placeholder in remaining:
                before, remaining = remaining.split(placeholder, 1)
                if before.strip():
                    content_parts.append(Safe(before))
                content_parts.append(component)

        # Add any remaining content
        if remaining.strip():
            content_parts.append(Safe(remaining))

        # If no components, just show rendered content
        if not content_parts:
            content_parts = [Safe(rendered_md)]

        # Create AccordionItem with processed content
        accordion_items.append(
            AccordionItem(
                title,
                *content_parts,
                open=is_first  # First item expanded by default
            )
        )

    print(f"[DEBUG] Generated {len(accordion_items)} accordion items")

    # Return MonsterUI Accordion component with all items
    return Div(
        Accordion(
            *accordion_items,
            multiple=True,  # Allow multiple items to be open at once
            animation=True,  # Enable smooth animations
            duration=200  # Animation duration in ms
        ),
        cls="my-4"
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
    elif component_type == 'grid':
        return generate_mui_grid(tag_info, session_id)
    elif component_type == 'stat':
        return generate_mui_stat(tag_info, session_id)
    elif component_type == 'table':
        return generate_mui_table(tag_info, session_id)
    elif component_type == 'tabs':
        return generate_mui_tabs(tag_info, session_id)
    elif component_type == 'accordion':
        return generate_mui_accordion(tag_info, session_id)
    else:
        # Unknown type, return empty div
        return Div()

# ============================================================================
# MUI Tag Processing
# ============================================================================

def process_mui_tags(content: str, session_id: str) -> tuple[list[Any], str]:
    """Process MUI tags in content and return components + cleaned markdown"""
    # Find all MUI tags with regex to get positions
    mui_pattern: str = r'<mui[^>]*>.*?</mui>'
    matches: list[re.Match[str]] = list(re.finditer(mui_pattern, content, re.DOTALL))

    if not matches:
        return [], content

    # Parse the tags
    mui_tags, _ = parse_mui_tags(content)

    # Build components and create placeholders (use HTML comments that markdown preserves)
    components: list[Any] = []
    result_content: str = content

    for i, (match, tag_info) in enumerate(zip(reversed(matches), reversed(mui_tags))):
        component = generate_mui_component(tag_info, session_id)
        components.insert(0, component)

        # Replace the MUI tag with an HTML comment placeholder
        placeholder = f"<!--MUI_COMPONENT_{i}-->"
        result_content = result_content[:match.start()] + placeholder + result_content[match.end():]

    return components, result_content
