# LexiForge

## Обзор

LexiForge — это десктопный прототип для изучения языков с помощью ИИ, построенный на `PySide6`, `Qt WebEngine` и HTML/CSS/JavaScript UI. Приложение позволяет учащемуся описать, что именно он хочет изучать, а затем собирает на основе этого урок.

## Структура проекта

```text
LexiForge/
|-- main.py                         # Точка входа приложения
|-- settings.yaml                   # Runtime-настройки языков, моделей и параметров пайплайна
|-- app/                            # Оболочка приложения, маршрутизация, логирование и настройки
|   |-- backend.py
|   |-- router.py
|   |-- settings.py
|   |-- logging_config.py
|   |-- exception_logging.py
|   `-- language_registry.py
|-- models/                         # Типизированные модели карточек, шагов макроплана и сгенерированных упражнений
|-- pipeline/                       # Генерация словаря, макропланирование урока, генерация заданий и парсинг
|-- llm_gateway/                    # Обёртки над OpenAI-клиентом и вспомогательные инструменты кэша
|-- prompts/                        # Шаблоны промптов, используемые пайплайном генерации
|-- dev_fixtures/                   # Необязательные локальные фикстуры для разработки и отладки
|-- ui/
|   |-- controllers/                # Контроллеры экранов, включая настройку, загрузку и сценарий урока
|   |-- services/                   # Фоновые воркеры и сервисы на стороне UI
|   |-- views/                      # HTML/CSS/JS-экраны
|   `-- assets/                     # Общие темы и статические ресурсы
`-- i18n/                           # Локализованная документация проекта
```

## Как это работает

1. Учащийся вводит запрос на изучение в стартовом экране.
2. Приложение генерирует словарные карточки и показывает их в интерфейсе по мере поступления.
3. Когда пользователь запускает урок, приложение открывает экран загрузки.
4. Фоновый воркер создаёт макроплан урока на основе выбранных карточек.
5. Генератор заданий разворачивает этот план в конкретные упражнения для экрана прохождения урока.

## Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/Glebhl/LexiForge.git
cd LexiForge
```

### 2. Создайте и активируйте виртуальное окружение

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Установите зависимости

```bash
pip install -r requirements.txt
```

### 4. Настройте переменные окружения

Создайте файл `.env` в корне проекта:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Без `OPENAI_API_KEY` генерация карточек и живая генерация уроков работать не будут.

### 5. При необходимости скорректируйте runtime-настройки

Отредактируйте `settings.yaml`, чтобы выбрать языки урока, уровень ученика, назначение моделей и параметры пайплайна:

```yaml
lesson:
  language: en
  lerner_language: ru
  learner_level: B2
models:
  card_generation: gpt-5.4-nano
  lesson_planning: o3
  task_generation: gpt-5.4-mini
  answer_matcher: gpt-5.4-nano
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

### 6. Запустите приложение

```bash
python main.py
```

## Заметки для разработки

- `dev_fixtures` может заранее подгружать карточки или подменять живую генерацию урока fixture-данными во время разработки.
- Файлы промптов в `prompts/en/` управляют как макропланированием, так и генерацией заданий.

Для отладки можно добавить в `.env` такие параметры:

```env
GLOSIUM_DEV_CARDS=1
GLOSIUM_DEV_MACRO_PLAN=1
GLOSIUM_DEV_LESSON=1
GLOSIUM_DEV_CARDS_FILE=dev_fixtures/cards.json
GLOSIUM_DEV_MACRO_PLAN_FILE=dev_fixtures/macro_plan.txt
GLOSIUM_DEV_LESSON_FILE=dev_fixtures/lesson.json
```

## Статус

Проект всё ещё находится на стадии прототипа. Текущая версия поддерживает только генерацию словаря с помощью ИИ.

## Дорожная карта

Блтжайшие планы:

- Добавить ИИ-подсказки и объяснения ошибок
- Добавить поддержку большего числа языков
- Добавить поддержку грамматики
- Добавить локализации помимо английского
- Добавить отслеживание прогресса

## Вклад в проект

Issues, предложения и pull request'ы приветствуются.
