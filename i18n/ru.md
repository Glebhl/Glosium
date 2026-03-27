# LexiForge

LexiForge — это десктопный прототип приложения для изучения языков на `PySide6`, `Qt WebEngine` и HTML/CSS/JavaScript. Пользователь описывает, что хочет изучать, приложение генерирует словарные карточки через OpenAI и затем запускает урок на их основе.

## Текущие возможности

- Генерация словарных карточек через OpenAI Responses API
- Учебный сценарий с заданиями типов explanation, matching, translation, filling и question
- Dev-fixtures для карточек, макроплана и временного плана урока

## Структура проекта

```text
LexiForge/
|-- main.py                         # Точка входа приложения
|-- app/                            # Инфраструктура приложения и общие runtime-утилиты
|   |-- backend.py                  # Мост между Python и UI через Qt
|   |-- router.py                   # Навигация между экранами
|   |-- logging_config.py           # Настройка логирования
|   |-- exception_logging.py        # Глобальное логирование исключений и callback-ошибок
|   `-- language_registry.py        # Справочник языков и helper-функции
|-- dev_fixtures/                   # Локальные fixture-данные и настройки их загрузки
|   |-- settings.py
|   |-- cards.json
|   |-- macro_plan.txt
|   `-- lesson.json
|-- llm_gateway/                    # Обертки над OpenAI и кэш
|-- pipeline/                       # Генерация карточек, планов и заданий
|-- prompts/                        # Шаблоны промптов
`-- ui/
    |-- controllers/                # Контроллеры экранов
    |-- services/                   # Вспомогательные сервисы для UI-слоя
    |-- views/                      # HTML/CSS/JS экраны
    `-- assets/                     # Шрифты, иконки и общие стили
```

## Быстрый старт

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```
