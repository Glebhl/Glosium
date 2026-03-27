from importlib import import_module

__all__ = [
    "VocabularyCard",
    "VocabularyCardGenerator",
    "MacroPlanner",
    "TaskGenerator",
    "FillingTaskGenerator",
    "MatchingTaskGenerator",
    "QuestionTaskGenerator",
    "TranslationTaskGenerator",
    "AnswerMatcher",
]

_EXPORT_MAP = {
    "VocabularyCard": (".card_models", "VocabularyCard"),
    "VocabularyCardGenerator": (".card_generation", "VocabularyCardGenerator"),
    "MacroPlanner": (".lesson_planning", "MacroPlanner"),
    "TaskGenerator": (".macro_plan_task_generation", "TaskGenerator"),
    "FillingTaskGenerator": (".task_generation", "FillingTaskGenerator"),
    "MatchingTaskGenerator": (".task_generation", "MatchingTaskGenerator"),
    "QuestionTaskGenerator": (".task_generation", "QuestionTaskGenerator"),
    "TranslationTaskGenerator": (".task_generation", "TranslationTaskGenerator"),
    "AnswerMatcher": (".answer_matcher", "AnswerMatcher"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
