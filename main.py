import logging
import sys

from dotenv import load_dotenv
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from app import Backend
from app import Router
from app import install_global_exception_logging
from app import setup_logging
from ui.controllers import LessonSetupController

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window that hosts the WebEngine view and JS <-> Python bridge."""

    def __init__(self) -> None:
        super().__init__()
        logger.debug("MainWindow initialization started")

        self._configure_window()
        self._create_web_view()
        self._init_backend_and_routing()
        self._init_web_channel()
        self._open_initial_page()

        logger.info("MainWindow initialization completed")

    def _configure_window(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("PySide6 + WebEngine")

    def _create_web_view(self) -> None:
        """Create and attach the WebEngine view."""
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)
        logger.debug("WebEngine view created and set as central widget")

    def _init_backend_and_routing(self) -> None:
        """Initialize backend bridge object and router."""
        self.backend = Backend()
        logger.debug("Backend object created")

        self.router = Router(self.web_view, self.backend)
        logger.debug("Router created")

    def _init_web_channel(self) -> None:
        """Initialize QWebChannel for JS <-> Python communication."""
        self.web_channel = QWebChannel(self.web_view.page())
        self.web_channel.registerObject("backend", self.backend)
        self.web_view.page().setWebChannel(self.web_channel)
        logger.debug("WebChannel configured and backend registered as 'backend'")

    def _open_initial_page(self) -> None:
        """Navigate to the initial controller/page."""
        self.router.navigate_to(LessonSetupController)
        logger.debug("Navigated to VocabPlannerController")


def main() -> int:
    """Application entry point."""
    setup_logging(logging.DEBUG, log_to_file=True)
    install_global_exception_logging(logger)

    logger.debug("dotenv initialization")
    load_dotenv()
    logger.debug("dotenv was initializated")

    logger.debug("Application startup")

    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.resize(1200, 860)
    main_window.setMinimumSize(700, 500)
    main_window.show()

    logger.info("Application started successfully")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
