# LexiForge

LexiForge is an open-source desktop application for language learning.

This repository is currently in a very early stage.

## Project Layout

```text
LexiForge/
├─ main.py                     # Application entry point
├─ backend.py                  # Python <-> UI bridge via Qt signals/slots
├─ router.py                   # Screen navigation and transitions
├─ answer_matcher.py           # Text normalization and answer matching
├─ lesson_plans/               # Lesson content in JSON format
├─ pages/                      # Python backend for web screens
│  ├─ lesson.py                # Lesson flow, task loading, answer checks
│  └─ vocab_setup.py           # Vocabulary setup screen logic
└─ UI/                         # Frontend screens, styles, assets, and scripts
```

## How It Works

When the application starts, `main.py` creates a `PySide6` window with an embedded browser view. The interface itself is built with HTML/CSS/JavaScript. Python controllers load screens, react to UI events through `QWebChannel`, and validate some lesson answers.

Right now, lessons are loaded from temporary test templates stored in JSON files [`lesson_plans`](./lesson_plans). In the future, lessons will be automatically generated with AI based on the learner's request.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Glebhl/LexiForge.git
cd LexiForge
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

### 4. Run the app

```bash
python main.py
```


## Lesson Format

Lessons are defined as arrays of task objects. A task usually contains:

- `task_id` to select the task type
- `content` for the task payload
- `answers` for accepted solutions, when validation is needed

See [`lesson_plans/lesson.json`](./lesson_plans/lesson.json) for an example.

## Roadmap

The planned direction of the project is to turn the main screen into a lesson builder. A user will be able to enter a request, create a list of vocabulary cards, and use that input as the basis for an AI-generated personalized lesson.

The current prototype is focused mostly on vocabulary-oriented lesson flow, but the long-term plan is to support more areas of language learning, including:

- Grammar
- Speaking practice
- Writing practice
- Listening practice
- Additional exercise types

At the moment, only English is supported. Planned future language support is roughly expected in this order:

1. German
2. Polish
3. Japanese
4. Russian
5. Spanish
6. Italian
7. French

## Status

This is a work-in-progress open-source project in a very early version. The current application is mostly a prototype of the lesson engine, desktop shell, and interface flow. Some parts of the product are still based on temporary test data and placeholder content.

## Contributing

Issues, suggestions, and pull requests are welcome.

## TODO

- [ ] Fill out this TODO list
