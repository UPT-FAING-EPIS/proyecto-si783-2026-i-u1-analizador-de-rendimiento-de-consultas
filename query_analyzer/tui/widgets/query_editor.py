"""Query editor widget for interactive analysis screen."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Label, TextArea


class QueryEditor(Container):
    """Multi-line query editor with syntax highlighting and analyze action."""

    DEFAULT_CSS = """
    QueryEditor {
        width: 1fr;
        height: 16;
        min-height: 16;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }

    QueryEditor:focus {
        border: solid $accent;
    }

    QueryEditor > Label {
        margin-bottom: 1;
        text-style: bold;
    }

    QueryEditor TextArea {
        height: 1fr;
        border: solid $surface-lighten-2;
        overflow-y: auto;
    }
    """

    def __init__(self, language: str = "sql") -> None:
        super().__init__(id="query-editor")
        self._language = language

    def compose(self) -> ComposeResult:
        yield Label("Query:")
        yield TextArea.code_editor(
            text="",
            language=self._language,
            id="query-input",
        )

    def focus_editor(self) -> None:
        self.query_one("#query-input", TextArea).focus()

    def is_query_focused(self) -> bool:
        """Check if query editor has focus."""
        text_area = self.query_one("#query-input", TextArea)
        return bool(text_area.has_focus)

    @property
    def query_text(self) -> str:
        return str(self.query_one("#query-input", TextArea).text)

    def set_query_text(self, text: str) -> None:
        editor = self.query_one("#query-input", TextArea)
        editor.text = text
        editor.focus()

    def set_language(self, language: str) -> None:
        editor = self.query_one("#query-input", TextArea)
        editor.language = language

    def set_busy(self, is_busy: bool) -> None:
        self.query_one("#query-input", TextArea).disabled = is_busy
