from textual.message import Message

class StatusUpdate(Message):
    """A message to update the status bar."""
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()
