# PromptPane

A modern chatbot application with a beautiful UI built using FastHTML, MonsterUI, and powered by Groq's lightning-fast LLM inference.

## Features

- Clean, responsive chat interface
- Real-time message streaming
- Conversation history
- Beautiful UI components from MonsterUI
- Fast responses powered by Groq's infrastructure
- Session-based conversations

## Quick Start

### Prerequisites

- Python 3.8 or higher
- A Groq API key (get one at [console.groq.com](https://console.groq.com/keys))

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

## License

Apache License 2.0
