from __future__ import annotations
from typing import Any, Callable, Optional


class ContextTypes:
    DEFAULT_TYPE = object


class _ChatFilter:
    def __init__(self, chat_id: Optional[int] = None) -> None:
        self.chat_id = chat_id

    def __call__(self, update: "Update") -> bool:
        if self.chat_id is None:
            return True
        return getattr(getattr(update, "effective_chat", None), "id", None) == self.chat_id


class _FiltersModule:
    def Chat(self, chat_id: Optional[int] = None) -> _ChatFilter:
        return _ChatFilter(chat_id=chat_id)


filters = _FiltersModule()


class CommandHandler:
    def __init__(self, command: str, callback: Callable[..., Any], filters: Any = None) -> None:
        self.command = command
        self.callback = callback
        self.filters = filters


class ApplicationBuilder:
    def __init__(self) -> None:
        self._token: Optional[str] = None

    def token(self, token: str) -> "ApplicationBuilder":
        self._token = token
        return self

    def build(self) -> "Application":
        return Application(self._token)


class Application:
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token
        self.handlers: list[CommandHandler] = []
        self.bot_data: dict[str, Any] = {}

    @classmethod
    def builder(cls) -> ApplicationBuilder:
        return ApplicationBuilder()

    def add_handler(self, handler: CommandHandler) -> None:
        self.handlers.append(handler)

    async def initialize(self) -> None:
        return None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class Message:
    def __init__(self, text: str = "") -> None:
        self.text = text

    async def reply_text(self, text: str, parse_mode: Optional[str] = None) -> None:
        return None


class Update:
    def __init__(self, message: Optional[Message] = None) -> None:
        self.message = message
        self.effective_chat = None


class Bot:
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token

    async def send_message(self, chat_id: Any, text: str, parse_mode: Optional[str] = None) -> None:
        return None
