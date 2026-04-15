# Channel Protocol

```python
class Channel(Protocol):
    async def start(self, handler: MessageHandler) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, chat_id: str, widget: Widget) -> None: ...
```

## InboundMessage

Normalized across all transports:

```python
InboundMessage(channel, chat_id, sender_id, text, metadata)
```

## Widget

```python
Widget(type, content)
```

Types: `text`, `file`, `quiz_url`, `flashcard_url`. Each channel decides
how to render; see [channels/telegram/widgets.py](../channels/telegram/widgets.py)
for the reference implementation.

## Lifecycle

1. Runtime constructs the channel.
2. Calls `await channel.start(router.on_message)`.
3. Channel drives inbound messages through the handler.
4. On shutdown, runtime calls `await channel.stop()`.
