"""
Unit tests for utils.py

Tests for citation extraction, formatting, and LaTeX processing.
"""

import pytest
from utils import (
    extract_citation_urls,
    make_citations_clickable,
    extract_latex,
    restore_latex
)
from unittest.mock import Mock

# ============================================================================
# Citation Extraction Tests
# ============================================================================

@pytest.mark.unit
class TestExtractCitationUrls:
    """Tests for extract_citation_urls()"""

    def test_extract_citations_from_valid_response(self):
        """Test extraction of citations from valid API response"""
        # Mock Groq API response
        mock_completion = Mock()
        mock_message = Mock()
        mock_tool = Mock()
        mock_result = Mock()

        # Set up mock structure
        mock_result.url = "https://example.com"
        mock_result.title = "Example Title"
        mock_search_results = Mock()
        mock_search_results.results = [mock_result]

        mock_tool.type = 'browser_search'
        mock_tool.search_results = mock_search_results

        mock_message.executed_tools = [mock_tool]
        mock_completion.choices = [Mock(message=mock_message)]

        # Test extraction
        result = extract_citation_urls(mock_completion)

        assert 0 in result
        assert result[0]['url'] == "https://example.com"
        assert result[0]['title'] == "Example Title"

    def test_extract_citations_multiple_results(self):
        """Test extraction of multiple citations"""
        mock_completion = Mock()
        mock_message = Mock()
        mock_tool = Mock()

        # Create multiple search results
        results = []
        for i in range(3):
            mock_result = Mock()
            mock_result.url = f"https://example{i}.com"
            mock_result.title = f"Title {i}"
            results.append(mock_result)

        mock_search_results = Mock()
        mock_search_results.results = results

        mock_tool.type = 'browser_search'
        mock_tool.search_results = mock_search_results
        mock_message.executed_tools = [mock_tool]
        mock_completion.choices = [Mock(message=mock_message)]

        result = extract_citation_urls(mock_completion)

        assert len(result) == 3
        for i in range(3):
            assert i in result
            assert result[i]['url'] == f"https://example{i}.com"
            assert result[i]['title'] == f"Title {i}"

    def test_extract_citations_no_tools(self):
        """Test extraction when no tools were executed"""
        mock_completion = Mock()
        mock_message = Mock()
        mock_message.executed_tools = None
        mock_completion.choices = [Mock(message=mock_message)]

        result = extract_citation_urls(mock_completion)

        assert result == {}

    def test_extract_citations_no_browser_search(self):
        """Test extraction when tool is not browser_search"""
        mock_completion = Mock()
        mock_message = Mock()
        mock_tool = Mock()
        mock_tool.type = 'code_interpreter'

        mock_message.executed_tools = [mock_tool]
        mock_completion.choices = [Mock(message=mock_message)]

        result = extract_citation_urls(mock_completion)

        assert result == {}

    def test_extract_citations_handles_error_gracefully(self):
        """Test extraction handles errors gracefully"""
        # Invalid structure that will cause an error
        mock_completion = Mock()
        mock_completion.choices = []

        result = extract_citation_urls(mock_completion)

        assert result == {}

# ============================================================================
# Citation Formatting Tests
# ============================================================================

@pytest.mark.unit
class TestMakeCitationsClickable:
    """Tests for make_citations_clickable()"""

    def test_simple_citation_replacement(self):
        """Test simple citation marker is replaced with link"""
        content = "This is a fact【0†L10-L12】that needs citation."
        citation_urls = {
            0: {
                'url': 'https://example.com',
                'title': 'Example Source - Details'
            }
        }

        result = make_citations_clickable(content, citation_urls)

        assert '【0†L10-L12】' not in result
        assert '<a href="https://example.com"' in result
        assert 'Example Source' in result
        assert 'target="_blank"' in result
        assert 'rel="noopener noreferrer"' in result

    def test_multiple_citations(self):
        """Test multiple citation markers are replaced"""
        content = "First【0†L1】second【1†L2】third【2†L3】"
        citation_urls = {
            0: {'url': 'https://example0.com', 'title': 'Source 0'},
            1: {'url': 'https://example1.com', 'title': 'Source 1'},
            2: {'url': 'https://example2.com', 'title': 'Source 2'}
        }

        result = make_citations_clickable(content, citation_urls)

        assert '【0†L1】' not in result
        assert '【1†L2】' not in result
        assert '【2†L3】' not in result
        assert 'https://example0.com' in result
        assert 'https://example1.com' in result
        assert 'https://example2.com' in result

    def test_citation_without_url_preserved(self):
        """Test citation marker without matching URL is preserved"""
        content = "This has【5†L10】no matching URL."
        citation_urls = {
            0: {'url': 'https://example.com', 'title': 'Source'}
        }

        result = make_citations_clickable(content, citation_urls)

        # Citation 5 has no URL, so should be preserved
        assert '【5†L10】' in result

    def test_no_citations_returns_original(self):
        """Test content without citations returns unchanged"""
        content = "This has no citations."
        citation_urls = {}

        result = make_citations_clickable(content, citation_urls)

        assert result == content

    def test_empty_citation_urls_returns_original(self):
        """Test empty citation_urls dict returns original content"""
        content = "This has【0†L1】a citation."
        citation_urls = {}

        result = make_citations_clickable(content, citation_urls)

        assert result == content

    def test_title_extraction_with_dash(self):
        """Test source name extraction from title with dash"""
        content = "Text【0†L1】here."
        citation_urls = {
            0: {'url': 'https://example.com', 'title': 'Short Name - Long Details About Topic'}
        }

        result = make_citations_clickable(content, citation_urls)

        # Should show short name in visible text
        assert '[Short Name]' in result
        # Full title should be in title attribute (for tooltip)
        assert 'title="Short Name - Long Details About Topic"' in result

    def test_title_extraction_with_pipe(self):
        """Test source name extraction from title with pipe"""
        content = "Text【0†L1】here."
        citation_urls = {
            0: {'url': 'https://example.com', 'title': 'Source Name | Website Name'}
        }

        result = make_citations_clickable(content, citation_urls)

        # Should show short name in visible text
        assert '[Source Name]' in result
        # Full title should be in title attribute (for tooltip)
        assert 'title="Source Name | Website Name"' in result

    def test_long_title_uses_domain(self):
        """Test very long title falls back to domain name"""
        content = "Text【0†L1】here."
        long_title = "A" * 60  # Longer than 50 chars
        citation_urls = {
            0: {'url': 'https://www.example.com/path', 'title': long_title}
        }

        result = make_citations_clickable(content, citation_urls)

        # Should use domain in visible text (not long title)
        assert '[example.com]' in result
        # Full title should still be in title attribute
        assert f'title="{long_title}"' in result
        # Check that www. is removed from visible text
        assert '[www.example.com]' not in result

# ============================================================================
# LaTeX Extraction Tests
# ============================================================================

@pytest.mark.unit
class TestExtractLatex:
    """Tests for extract_latex()"""

    def test_extract_display_math_double_dollar(self):
        """Test extraction of display math with $$...$$"""
        content = "Text $$E = mc^2$$ more text"

        result_content, latex_blocks = extract_latex(content)

        assert len(latex_blocks) == 1
        assert latex_blocks[0][0] == 'display'
        assert latex_blocks[0][1] == '$$E = mc^2$$'
        assert '<!--LATEX_BLOCK_0-->' in result_content

    def test_extract_display_math_square_brackets(self):
        """Test extraction of display math with \\[...\\]"""
        content = r"Text \[E = mc^2\] more text"

        result_content, latex_blocks = extract_latex(content)

        assert len(latex_blocks) == 1
        assert latex_blocks[0][0] == 'display'
        assert latex_blocks[0][1] == r'\[E = mc^2\]'

    def test_extract_inline_math_single_dollar(self):
        """Test extraction of inline math with $...$"""
        content = "Text $E = mc^2$ more text"

        result_content, latex_blocks = extract_latex(content)

        assert len(latex_blocks) == 1
        assert latex_blocks[0][0] == 'inline'
        assert '$E = mc^2$' in latex_blocks[0][1]

    def test_extract_inline_math_parentheses(self):
        """Test extraction of inline math with \\(...\\)"""
        content = r"Text \(E = mc^2\) more text"

        result_content, latex_blocks = extract_latex(content)

        assert len(latex_blocks) == 1
        assert latex_blocks[0][0] == 'inline'
        assert latex_blocks[0][1] == r'\(E = mc^2\)'

    def test_extract_multiple_math_blocks(self):
        """Test extraction of multiple math blocks"""
        content = "Display $$a^2$$ and inline $b^2$ and $$c^2$$"

        result_content, latex_blocks = extract_latex(content)

        assert len(latex_blocks) == 3
        assert all(block[1] for block in latex_blocks)  # All have content

    def test_extract_no_math_returns_unchanged(self):
        """Test content without math returns unchanged"""
        content = "Just plain text with no math"

        result_content, latex_blocks = extract_latex(content)

        assert result_content == content
        assert latex_blocks == []

    def test_extract_complex_latex(self):
        """Test extraction of complex LaTeX expression"""
        content = r"The formula $$\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$ is quadratic"

        result_content, latex_blocks = extract_latex(content)

        assert len(latex_blocks) == 1
        assert r'\frac' in latex_blocks[0][1]
        assert r'\sqrt' in latex_blocks[0][1]

    def test_extract_nested_delimiters(self):
        """Test $ inside $$ is handled correctly"""
        content = "Text $$\text{cost is $5}$$ more"

        result_content, latex_blocks = extract_latex(content)

        # Should extract the $$ block
        assert len(latex_blocks) >= 1
        assert '<!--LATEX_BLOCK' in result_content

# ============================================================================
# LaTeX Restoration Tests
# ============================================================================

@pytest.mark.unit
class TestRestoreLatex:
    """Tests for restore_latex()"""

    def test_restore_single_block(self):
        """Test restoration of single LaTeX block"""
        content = "Text <!--LATEX_BLOCK_0--> more text"
        latex_blocks = [('display', '$$E = mc^2$$')]

        result = restore_latex(content, latex_blocks)

        assert '<!--LATEX_BLOCK_0-->' not in result
        assert '$$E = mc^2$$' in result

    def test_restore_multiple_blocks(self):
        """Test restoration of multiple LaTeX blocks"""
        content = "A <!--LATEX_BLOCK_0--> and B <!--LATEX_BLOCK_1--> and C <!--LATEX_BLOCK_2-->"
        latex_blocks = [
            ('display', '$$a^2$$'),
            ('inline', '$b^2$'),
            ('display', '$$c^2$$')
        ]

        result = restore_latex(content, latex_blocks)

        assert '<!--LATEX_BLOCK' not in result
        assert '$$a^2$$' in result
        assert '$b^2$' in result
        assert '$$c^2$$' in result

    def test_restore_no_blocks(self):
        """Test restoration with no blocks returns unchanged"""
        content = "Plain text"
        latex_blocks = []

        result = restore_latex(content, latex_blocks)

        assert result == content

    def test_restore_preserves_order(self):
        """Test restoration preserves correct order"""
        content = "<!--LATEX_BLOCK_0--> then <!--LATEX_BLOCK_1-->"
        latex_blocks = [
            ('inline', '$first$'),
            ('inline', '$second$')
        ]

        result = restore_latex(content, latex_blocks)

        first_pos = result.find('$first$')
        second_pos = result.find('$second$')
        assert first_pos < second_pos

# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.unit
class TestLatexRoundTrip:
    """Integration tests for extract and restore LaTeX"""

    def test_extract_and_restore_roundtrip(self):
        """Test extracting and restoring LaTeX preserves content"""
        original = "Text with $$E = mc^2$$ and $F = ma$ formulas"

        # Extract
        processed, blocks = extract_latex(original)

        # Restore
        restored = restore_latex(processed, blocks)

        # Should match original
        assert restored == original

    def test_roundtrip_with_multiple_types(self):
        """Test roundtrip with different LaTeX delimiter types"""
        original = r"Display $$x^2$$ inline $y^2$ brackets \[z^2\] parens \(w^2\)"

        processed, blocks = extract_latex(original)
        restored = restore_latex(processed, blocks)

        # All LaTeX should be preserved
        assert '$$x^2$$' in restored
        assert '$y^2$' in restored
        assert r'\[z^2\]' in restored
        assert r'\(w^2\)' in restored
