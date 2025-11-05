"""
PromptPane Configuration

This module contains all configuration settings for the application including:
- Server configuration
- Groq API settings
- Retry logic parameters
- Logging configuration
- External CDN resources
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# Server Configuration
# ============================================================================

SERVER_PORT: int = 5001
"""Port number for the FastHTML server"""

DEFAULT_SESSION_ID: str = "default"
"""Default session ID for conversations"""

# ============================================================================
# Groq API Configuration
# ============================================================================

GROQ_API_KEY: Optional[str] = os.environ.get("GROQ_API_KEY")
"""Groq API key from environment variables"""

GROQ_MODEL: str = "openai/gpt-oss-120b"
"""Groq model to use for chat completions"""

GROQ_TEMPERATURE: float = 0.7
"""Temperature setting for model responses (0.0-1.0)"""

GROQ_TOOLS: list[dict[str, str]] = [
    {"type": "browser_search"},
    {"type": "code_interpreter"}
]
"""Tools available to the Groq API"""

# ============================================================================
# Retry Logic Configuration
# ============================================================================

RETRY_MAX_ATTEMPTS: int = 3
"""Maximum number of retry attempts for transient failures"""

RETRY_INITIAL_DELAY: int = 1
"""Initial delay in seconds before first retry"""

RETRY_MAX_DELAY: int = 10
"""Maximum delay in seconds between retries"""

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL: str = "INFO"
"""Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"""

LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
"""Format string for log messages"""

# ============================================================================
# External CDN Resources - KaTeX for LaTeX Rendering
# ============================================================================

KATEX_VERSION: str = "0.16.9"
"""KaTeX library version"""

KATEX_CSS_URL: str = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
KATEX_CSS_INTEGRITY: str = "sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV"

KATEX_JS_URL: str = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"
KATEX_JS_INTEGRITY: str = "sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8"

KATEX_AUTORENDER_URL: str = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/contrib/auto-render.min.js"
KATEX_AUTORENDER_INTEGRITY: str = "sha384-+VBxd3r6XgURycqtZ117nYw44OOcIax56Z4dCRWbxyPt0Koah1uHoK0o4+/RRE05"

# ============================================================================
# UI Theme Configuration
# ============================================================================

THEME_COLOR: str = "blue"
"""MonsterUI theme color"""

ENABLE_SYNTAX_HIGHLIGHTING: bool = True
"""Enable syntax highlighting in code blocks"""

ENABLE_LIVE_RELOAD: bool = True
"""Enable live reload during development"""

# ============================================================================
# Citation Link Styling
# ============================================================================

CITATION_CSS: str = """
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
"""
"""CSS styling for citation links"""

# ============================================================================
# Input Validation & Security
# ============================================================================

MAX_MESSAGE_LENGTH: int = 10000
"""Maximum allowed message length in characters"""

MIN_MESSAGE_LENGTH: int = 1
"""Minimum allowed message length in characters"""

MAX_SESSION_ID_LENGTH: int = 100
"""Maximum allowed session ID length"""

SESSION_ID_PATTERN: str = r'^[a-zA-Z0-9_-]+$'
"""Regex pattern for valid session IDs (alphanumeric, underscore, hyphen)"""

RATE_LIMIT_WINDOW_SECONDS: int = 60
"""Time window for rate limiting in seconds"""

RATE_LIMIT_MAX_REQUESTS: int = 10
"""Maximum requests allowed per session within the time window"""

ENABLE_RATE_LIMITING: bool = True
"""Enable rate limiting for API requests"""
