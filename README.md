# LexiForge

## Localizations

- [Русский](i18n/ru.md)
- [Español](i18n/es.md)
- [中文](i18n/zh.md)

## Short Overview

LexiForge is a desktop prototype for language learning built with `PySide6`, `Qt WebEngine`, and an HTML/CSS/JavaScript UI. The app lets a learner describe what they want to study, generates vocabulary cards with OpenAI, and then launches a lesson flow based on the selected content.

## Current Capabilities

- Vocabulary card generation through the OpenAI Responses API
- Lesson flow with multiple task types: explanation, matching, translation, filling, and question
- Development fixtures for cards, macro plans, and temporary lesson plans

## Project Layout

```text
LexiForge/
|-- main.py                         # Application entry point
|-- app/                            # Application shell and shared runtime utilities
|   |-- backend.py                  # Python <-> UI bridge via Qt signals/slots
|   |-- router.py                   # Screen navigation and controller routing
|   |-- logging_config.py           # Logging setup
|   |-- exception_logging.py        # Global exception and callback logging
|   `-- language_registry.py        # Language labels and lookup helpers
|-- dev_fixtures/                   # Local fixture data and fixture loading settings
|   |-- settings.py
|   |-- cards.json
|   |-- macro_plan.txt
|   `-- lesson.json
|-- llm_gateway/                    # OpenAI client wrappers and cache helpers
|-- pipeline/                       # Lesson and task generation pipeline
|-- prompts/                        # Prompt templates
`-- ui/
    |-- controllers/                # Screen controllers
    |-- services/                   # Controller-adjacent UI services
    |-- views/                      # HTML/CSS/JS screens
    `-- assets/                     # Fonts, icons, shared theme files
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Glebhl/LexiForge.git
cd LexiForge
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root and add your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Without `OPENAI_API_KEY`, vocabulary generation will not work.

### 5. Run the app

```bash
python main.py
```

## Status

This project is still an early prototype. The vocabulary setup flow already uses OpenAI, while the full lesson generation pipeline is still partially backed by temporary JSON lesson data.

## Roadmap

Planned next steps include:

- Generate full lessons from the selected vocabulary cards
- Add support for more languages
- Add grammar support
- Add localization other than English
- Replace temporary lesson templates with fully AI-driven lesson creation
- Add progress tracking

## Contributing

Issues, suggestions, and pull requests are welcome.
