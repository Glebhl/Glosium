# Glosium

Glosium is a desktop prototype for AI-assisted language learning built with `pywebview` and an HTML/CSS/JavaScript UI. The app lets a learner describe what they want to study and then builds a lesson from that.

## Project Layout

```text
Glosium/
|-- main.py                         # Application entry point
|-- settings.yaml                   # Runtime settings for languages, models, and pipeline options
|-- app/                            # Application shell, routing, logging, and settings helpers
|   |-- backend.py
|   |-- router.py
|   |-- settings.py
|   |-- logging_config.py
|-- models/                         # Typed models for cards, macro plan steps, and generated exercises
|-- pipeline/                       # Vocabulary generation, macro planning, task generation, and parsing
|-- llm_gateway/                    # Provider-agnostic LLM gateway and provider adapters
|-- prompts/                        # Prompt templates used by the generation pipeline
|-- dev_fixtures/                   # Optional local fixtures for development and debugging
|-- ui/
|   |-- controllers/                # Screen controllers, including setup, loading, and lesson flow
|   |-- services/                   # Background workers and UI-side services
|   |-- views/                      # HTML/CSS/JS screens
|   `-- assets/                     # Shared theme files and static assets
`-- i18n/                           # Localized project documentation
```

## How It Works

1. The learner enters a study request in the setup screen.
2. The app generates vocabulary cards and shows them in the UI as they arrive.
3. When the learner starts the lesson, the app opens a loading screen.
4. A background worker creates a macro lesson plan from the selected cards.
5. The task generator expands that plan into concrete lesson exercises for the lesson flow screen.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Glebhl/Glosium.git
cd Glosium
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Without `OPENAI_API_KEY`, card generation and live lesson generation will not work.

### 5. Adjust runtime settings

Edit `settings.yaml` to choose lesson languages, learner level, model assignments, and pipeline options. Models now use the `provider:model` format so the gateway can support more backends later:

```yaml
lesson:
  language: en
  lerner_language: ru
  learner_level: B2
models:
  card_generation: openai:gpt-5.4-nano
  lesson_planning: openai:o3
  task_generation: openai:gpt-5.4-mini
  answer_matcher: openai:gpt-5.4-nano
pipeline:
  card_generation:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
  lesson_planning:
    reasoning_effort: low
    text_verbosity: null
    service_tier: flex
  task_generation:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
  answer_matcher:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
```

### 6. Run the app

```bash
python main.py
```

## Development Notes

- `dev_fixtures` can preload cards or replace live lesson generation with fixture data during development.
- Prompt files in `prompts/en/` drive both macro planning and task generation.

Set up .env file with this parameters for debugging
```env
GLOSIUM_DEV_CARDS=1
GLOSIUM_DEV_MACRO_PLAN=1
GLOSIUM_DEV_LESSON=1
GLOSIUM_DEV_CARDS_FILE=dev_fixtures/cards.json
GLOSIUM_DEV_MACRO_PLAN_FILE=dev_fixtures/macro_plan.txt
GLOSIUM_DEV_LESSON_FILE=dev_fixtures/lesson.json
```

## Status

The project is still a prototype. The current build supports only AI-driven vocabulary generation.

## Roadmap

Planned next steps include:

- Add AI guidance and explanations for mistakes
- Add support for more languages
- Add grammar support
- Add localizations other than English
- Add progress tracking

## Contributing

Issues, suggestions, and pull requests are welcome.
