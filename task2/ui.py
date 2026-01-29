# ui.py
"""Textual UI компоненты для Coding Agent"""

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Horizontal
from textual.widgets import Header, Footer, Input, Markdown, Static, LoadingIndicator
from textual.binding import Binding
from textual import on

from agent import run_agent_stream, parse_file_mentions


class ToolCallWidget(Static):
    """Виджет для отображения вызова инструмента"""

    DEFAULT_CSS = """
    ToolCallWidget {
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """


class FileMentionWidget(Static):
    """Виджет для отображения упомянутого файла"""

    DEFAULT_CSS = """
    FileMentionWidget {
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 1;
        margin: 0 0 0 2;
    }
    """


class MessageWidget(Static):
    """Виджет для отображения сообщения пользователя"""

    DEFAULT_CSS = """
    MessageWidget {
        background: $primary-darken-2;
        color: $text;
        padding: 1 2;
        margin: 0 0 1 0;
    }
    """


class AgentResponse(Markdown):
    """Виджет для ответа агента с поддержкой стриминга"""

    DEFAULT_CSS = """
    AgentResponse {
        background: $surface;
        padding: 1 2;
        margin: 0 0 1 0;
    }
    """


class ChatContainer(ScrollableContainer):
    """Контейнер для чата"""

    DEFAULT_CSS = """
    ChatContainer {
        height: 1fr;
        padding: 1;
    }
    """


class CodingAgentApp(App):
    """Coding Agent TUI"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto auto;
    }

    #input-container {
        dock: bottom;
        padding: 1;
        height: auto;
    }

    Input {
        width: 100%;
    }

    LoadingIndicator {
        height: 1;
        margin: 0 1;
    }

    #loading-container {
        height: 1;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Выход"),
        Binding("ctrl+l", "clear", "Очистить"),
    ]

    TITLE = "Coding Agent"
    SUB_TITLE = "Agno + Textual"

    def __init__(self, initial_command: str | None = None):
        super().__init__()
        self.is_processing = False
        self.initial_command = initial_command

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatContainer(id="chat")
        yield Static(id="loading-container")
        yield Horizontal(
            Input(placeholder="Введите сообщение...", id="input"),
            id="input-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        # Выполняем initial command если есть
        if self.initial_command:
            self.call_later(self.run_initial_command)

    async def run_initial_command(self) -> None:
        """Выполняет начальную команду"""
        if self.initial_command:
            await self.process_message(self.initial_command)

    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.is_processing:
            return

        message = event.value.strip()
        if not message:
            return

        if message.lower() in ("exit", "quit", "q"):
            self.exit()
            return

        # Очищаем input
        input_widget = self.query_one("#input", Input)
        input_widget.value = ""

        await self.process_message(message)

    async def process_message(self, message: str) -> None:
        """Обрабатывает сообщение пользователя"""
        chat = self.query_one("#chat", ChatContainer)
        input_widget = self.query_one("#input", Input)

        # Парсим file mentions для отображения
        _, files = parse_file_mentions(message)

        # Добавляем сообщение пользователя
        await chat.mount(MessageWidget(f"You: {message}"))

        # Показываем упомянутые файлы
        for filepath, content in files:
            status = "not found" if content == "[Файл не найден]" else f"{len(content)} chars"
            await chat.mount(FileMentionWidget(f"  @ {filepath} ({status})"))

        # Показываем loader
        self.is_processing = True
        loading_container = self.query_one("#loading-container", Static)
        loading = LoadingIndicator()
        await loading_container.mount(loading)

        # Создаём виджет для ответа
        response_widget = AgentResponse("")
        await chat.mount(response_widget)
        chat.scroll_end(animate=False)

        # Запускаем агента со стримингом
        try:
            full_content = ""
            async for chunk in run_agent_stream(message):
                if chunk.content:
                    full_content += chunk.content
                    await response_widget.update(full_content)
                    chat.scroll_end(animate=False)

                # Показываем tool calls
                if hasattr(chunk, 'tools') and chunk.tools:
                    for tool in chunk.tools:
                        tool_widget = ToolCallWidget(f"  {tool.name}({tool.args})")
                        await chat.mount(tool_widget, before=response_widget)

        except Exception as e:
            await response_widget.update(f"**Ошибка:** {e}")

        finally:
            # Убираем loader
            self.is_processing = False
            await loading.remove()

        chat.scroll_end(animate=False)
        input_widget.focus()

    def action_clear(self) -> None:
        """Очищает чат"""
        chat = self.query_one("#chat", ChatContainer)
        chat.remove_children()

    def action_quit(self) -> None:
        """Выход"""
        self.exit()
