"""Interactive Terminal User Interface for Mac Deep Cleaner."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Button, Label

class CleanerTUI(App):
    """A textual app to manage Mac Deep Cleaner."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    #main-container {
        layout: vertical;
        align: center middle;
        height: 100%;
    }
    #button-container {
        layout: horizontal;
        align: center middle;
        height: auto;
        margin: 2;
    }
    Button {
        margin: 1 2;
    }
    #title-label {
        text-align: center;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        padding: 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "action_scan", "Scan"),
        ("c", "action_clean", "Clean"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            yield Label("✨ Mac Deep Cleaner Interactive Mode ✨", id="title-label")
            with Horizontal(id="button-container"):
                yield Button("Scan System", id="btn-scan", variant="primary")
                yield Button("Clean Junk", id="btn-clean", variant="error")
                yield Button("Quit", id="btn-quit")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-quit":
            self.exit()
        elif event.button.id == "btn-scan":
            self.notify("Scanning functionality will be integrated soon!")
        elif event.button.id == "btn-clean":
            self.notify("Cleaning functionality will be integrated soon!")
            
def run_tui():
    app = CleanerTUI()
    app.run()
