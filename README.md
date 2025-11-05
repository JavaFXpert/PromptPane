# PromptPane

[![Tests](https://github.com/JavaFXpert/PromptPane/actions/workflows/test.yml/badge.svg)](https://github.com/JavaFXpert/PromptPane/actions/workflows/test.yml)
[![Code Quality](https://github.com/JavaFXpert/PromptPane/actions/workflows/lint.yml/badge.svg)](https://github.com/JavaFXpert/PromptPane/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/JavaFXpert/PromptPane/branch/main/graph/badge.svg)](https://codecov.io/gh/JavaFXpert/PromptPane)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A modern chatbot application with a beautiful UI built using FastHTML, MonsterUI, and powered by Groq's lightning-fast LLM inference.

## Features

### Core Functionality
- Clean, responsive chat interface
- Real-time message streaming
- Conversation history with session management
- Fast responses powered by Groq's infrastructure
- Interactive MUI components (buttons, sliders, text inputs, selects)
- LaTeX math rendering with KaTeX
- Clickable citation links from web search results

### Security & Validation
- Input validation for session IDs and messages
- Rate limiting (10 requests per 60 seconds per session)
- XSS prevention through HTML sanitization
- Path traversal protection
- Comprehensive error handling with retry logic

### Code Quality
- Type hints throughout codebase
- 99% test coverage (122 unit tests)
- Modular architecture (7 specialized modules)
- Automated CI/CD with GitHub Actions

## Quick Start

### Prerequisites

- Python 3.9 or higher
- A Groq API key (get one at [console.groq.com](https://console.groq.com/keys))
- pip (Python package installer)

### Installation

1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd PromptPane
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Groq API key:
   ```
   GROQ_API_KEY=your_api_key_here
   ```

4. Run the application:
   ```bash
   python main.py
   ```

5. Open your browser and navigate to `http://localhost:5001`

## Tech Stack

- **Frontend**: FastHTML, MonsterUI (FrankenUI + Tailwind + DaisyUI), HTMX
- **Backend**: Python, Groq API
- **LLM**: Llama 3.1 8B (via Groq)
- **Testing**: pytest, pytest-cov
- **Code Quality**: mypy, black, ruff, bandit

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
python -m pytest --cov=validators --cov=utils --cov=error_handling --cov=config --cov-report=term-missing

# Run specific test categories
pytest -m unit        # Unit tests only
pytest -m security    # Security tests only
pytest -m slow        # Slow tests only
```

### Code Quality Checks

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy config.py validators.py utils.py error_handling.py

# Security scanning
bandit -r .
```

### Development Setup

For development, install additional dependencies:

```bash
pip install -r requirements-dev.txt
```

## Project Structure

```
PromptPane/
├── main.py                 # FastHTML app and routes
├── config.py              # Configuration management
├── validators.py          # Input validation and rate limiting
├── utils.py               # Citation and LaTeX processing
├── error_handling.py      # Error handling and retry logic
├── constants.py           # System prompts and debug commands
├── mui_components.py      # MUI tag parsing and rendering
├── ui_components.py       # UI component definitions
├── tests/                 # Test suite (122 tests, 99% coverage)
│   ├── test_config.py
│   ├── test_validators.py
│   ├── test_utils.py
│   └── test_error_handling.py
├── .github/workflows/     # CI/CD pipelines
│   ├── test.yml          # Automated testing
│   └── lint.yml          # Code quality checks
└── requirements.txt       # Production dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run code quality checks (`black .`, `ruff check .`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

All PRs must:
- Pass all tests (122 tests)
- Maintain or improve code coverage (currently 99%)
- Pass linting and type checking
- Include tests for new functionality

## License

Apache License 2.0
