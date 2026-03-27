from __future__ import annotations

import json
import logging

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

logger = logging.getLogger(__name__)

class LessonSetupController(QObject):
    def __init__(self, router, view, backend):
        super().__init__()
        self.url = r"\ui\views\loading_screen\index.html"
        self.router = router
        self.view = view
        self.backend = backend
        self._handlers = {
            "btn-click": self._on_btn_click,
        }

    def on_load_finished(self):
        pass

    def on_ui_event(self, name: str, payload: dict):
        handler = self._handlers.get(name)
        if handler:
            handler(payload)

    def _run_js(self, function_name: str, *args: any) -> None:
        serialized_args = ", ".join(json.dumps(arg) for arg in args)
        self.view.page().runJavaScript(f"{function_name}({serialized_args});")

    def _on_btn_click(self, payload: dict):
        logger.debug("Clicked the button with the id='%s'", payload.get("id"))

        match payload.get("id"):
            case "stop":
                logger.info("Stooping lesson generation")

