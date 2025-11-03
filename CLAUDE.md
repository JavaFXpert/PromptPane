# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PromptPane is a chatbot application that dynamically generates UI controls with which users can respond. Built with FastHTML and MonsterUI on the frontend, and Groq for LLM inference on the backend.

## Key Documentation

The primary technical documentation is contained in `llms-ctx.txt`, which provides extensive API reference and examples for MonsterUI - a Python library for styling FastHTML apps with FrankenUI + Tailwind + DaisyUI components.

### MonsterUI Architecture

MonsterUI is organized into several key modules:

1. **monsterui.core** - Theme management (colors, radii, shadows, fonts) with CDN and local file support
2. **monsterui.daisy** - DaisyUI components (Alerts, Steps, Loading indicators, Toast notifications)
3. **monsterui.foundations** - Core utilities and data structures (VEnum, stringify)
4. **monsterui.franken** - Extensive FrankenUI component library including:
   - Typography (headings, text styles, presets)
   - Forms (inputs, selects, checkboxes, switches, textareas)
   - Layout (containers, grids, flexbox utilities, sections)
   - Navigation (navbars, sidebars, tabs, accordions)
   - Cards and tables
   - Modals and dropdowns
   - Icons and avatars
   - Charts (ApexCharts, Plotly integration)
   - Markdown rendering

### Component Patterns

MonsterUI follows FastHTML conventions:
- Components are Python functions returning FT (FastTag) objects
- Styling uses Enum classes (e.g., `ButtonT`, `TextT`, `CardT`, `TableT`)
- Components accept `*c` for children and `**kwargs` for HTML attributes
- Many components have compound structures (e.g., `Card` with header/body/footer)

### Example Applications

The documentation includes complete example applications demonstrating various UI patterns:
- Dashboard (data visualization, cards, charts)
- Forms (complex form layouts with validation)
- Authentication flows
- Mail client interface
- Task management with tables and filters
- Music player interface
- Help desk ticketing system
- Playground/IDE interface

## Development

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Groq API key
   ```
   Get your Groq API key from: https://console.groq.com/keys

3. **Run the application:**
   ```bash
   python main.py
   ```
   The app will be available at http://localhost:5001

### Architecture

**Frontend:**
- FastHTML for the web framework
- MonsterUI for UI components (FrankenUI + Tailwind + DaisyUI)
- HTMX for dynamic updates without page reloads

**Backend:**
- Groq API for LLM inference (using llama-3.1-8b-instant model)
- In-memory conversation storage (sessions isolated by session_id)

### Key Files

- `main.py` - Main application file with routes and chat logic
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (not committed to git)
- `llms-ctx.txt` - MonsterUI documentation and examples

## License

Apache License 2.0
