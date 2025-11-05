"""
PromptPane Utility Functions

This module contains utility functions for:
- Citation extraction and formatting
- LaTeX content processing
"""

import re
from urllib.parse import urlparse

# ============================================================================
# Citation Handling
# ============================================================================

def extract_citation_urls(chat_completion):
    """
    Extract URLs from browser_search tool results.

    Args:
        chat_completion: Groq API chat completion response object

    Returns:
        Dictionary mapping citation indices to URL and title information
    """
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
    """
    Replace citation markers with clickable links.

    Args:
        content: Text content containing citation markers like 【4†L716-L718】
        citation_urls: Dictionary mapping citation indices to URL/title info

    Returns:
        Content with citation markers replaced by HTML links
    """
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
                domain = urlparse(url).netloc
                # Remove 'www.' prefix if present
                source_name = domain.replace('www.', '')

            # Create user-friendly clickable link
            friendly_citation = f'[{source_name}]'
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="citation-link" title="{title}">{friendly_citation}</a>'
        else:
            return citation_text

    return re.sub(pattern, replace_citation, content)

# ============================================================================
# LaTeX Content Processing
# ============================================================================

def extract_latex(content):
    """
    Extract LaTeX blocks and replace with placeholders.

    This protects LaTeX content from markdown processing by temporarily
    replacing it with HTML comments, then restoring it afterward.

    Args:
        content: Text content that may contain LaTeX math expressions

    Returns:
        Tuple of (processed_content, latex_blocks)
        - processed_content: Content with LaTeX replaced by placeholders
        - latex_blocks: List of tuples (math_type, latex_content)
    """
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
    """
    Restore LaTeX blocks from placeholders.

    Replaces HTML comment placeholders with the original LaTeX content,
    leaving it raw for KaTeX to process on the client side.

    Args:
        content: Content with placeholder comments
        latex_blocks: List of tuples (math_type, latex_content) from extract_latex

    Returns:
        Content with LaTeX expressions restored
    """
    for i, (math_type, latex_content) in enumerate(latex_blocks):
        placeholder = f'<!--LATEX_BLOCK_{i}-->'
        # Restore LaTeX as-is, KaTeX will process it
        content = content.replace(placeholder, latex_content)

    return content
