from PySide6.QtCore import QObject
import random
import logging
from lesson_controller import LessonController

logger = logging.getLogger(__name__)

hints = [
    "specify level, topic, and format (<code>“with examples”</code>, <code>“phrasal verbs”</code>, <code>“medical terms”</code>).",
    "specify your level and goal (<code>“A2 travel”</code>, <code>“B1 conversation”</code>).",
    "choose a topic and format (<code>“food vocabulary”</code>).",  # TODO: Rewrite this tip
    "include the situation (<code>“at the airport”</code>, <code>“doctor appointment”</code>).",
    "request difficulty and pace (<code>“simple sentences”</code>, <code>“challenge me”</code>).",
    "focus on a grammar point (<code>“present perfect”</code>, <code>“conditionals”</code>).",
    "set the number of new words (<code>“teach 10 words”</code>, <code>“only 5 new words”</code>).",
    "pick a register (<code>“formal”</code>, <code>“casual”</code>, <code>“business”</code>).",
    "ask for phrasal verbs by theme (<code>“phrasal verbs for work”</code>, <code>“for travel”</code>).",
    "include your interests (<code>“music”</code>, <code>“gaming”</code>, <code>“fitness”</code>).",
    # "set a target skill (<code>“listening questions”</code>, <code>“reading practice”</code>).",
    # "request common mistakes to avoid (<code>“typical errors for B1”</code>, <code>“false friends”</code>).",
]

class VocabPlannerController(QObject):
    def __init__(self, router, view, backend):
        super().__init__()
        self.url = r"\UI\vocab-lesson-setup\index.html"
        self.router = router
        self.view = view
        self.backend = backend
        self.handlers = {
            "btn-click": self._on_btn_click,
            "card-closed": self._on_card_closed,
        }
        self.cards = []
    
    def on_load_finished(self):
        self.cards = []
        script = f'setHint("Tip: {random.choice(hints)}");'
        self.view.page().runJavaScript(script)

    def on_ui_event(self, name: str, payload: dict):
        handler = self.handlers.get(name)
        if handler:
            handler(payload)

    def _add_card(self, word, unit, part, level, transcription, translation, defenition, example):
        def get_card_id(id):
            logger.debug("Created a card with the id='%s'", id)
            card = {
                'word': word,
                'unit': unit,
                'part': part,
                'level': level,
                'transcription': transcription,
                'translation': translation,
                'defenition': defenition,
                'example': example
            }
            self.cards.append(card)
            
        script = f'addCard("{word}", "{unit}", "{part}", "{level}", "{transcription}", "{translation}", "{defenition}", "{example}");'
        self.view.page().runJavaScript(script, get_card_id)
    
    def _on_btn_click(self, payload: dict):
        logger.debug("Clicked the button with the id='%s'", payload.get("id"))

        match payload.get("id"):
            case "go":
                self._add_card("Humble", "word", "noun", "A2", "/ˈhʌmbl/", "скромный", "simple or ordinary; not special in any way", "“Despite his success, he stayed humble.”")
            case "start":
                # print(self.cards)
                self.router.navigate_to(LessonController)

    def _on_card_closed(self, payload: dict):
        self.cards.pop(int(payload['id']))
        logger.debug("The card #%s was closed by the UI", payload['id'])
