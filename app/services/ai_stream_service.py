"""
Streaming chat response with word-grouping and delay for a more natural, human-like stream.
Buffers Gemini chunks, sends every N words with a small delay (non-blocking).
"""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable, Awaitable

from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.services.ai_service import generate_chat_stream

logger = logging.getLogger(__name__)


def _sse_message(payload: dict) -> str:
    """Proper SSE format: data: {json}\\n\\n"""
    return f"data: {json.dumps(payload)}\n\n"


def _sync_producer(
    history: list[dict],
    message: str,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """
    Run in thread: sync Gemini stream; put each delta into queue via loop.
    Puts None when stream ends, or an Exception on error. Thread-safe: uses
    call_soon_threadsafe so we don't block the event loop.
    """
    try:
        for delta in generate_chat_stream(history, message):
            loop.call_soon_threadsafe(queue.put_nowait, delta)
        loop.call_soon_threadsafe(queue.put_nowait, None)
    except Exception as e:
        logger.exception("Gemini stream producer failed")
        loop.call_soon_threadsafe(queue.put_nowait, e)


def _take_words(buffer: str, n: int) -> tuple[str, str]:
    """
    Take up to n full words from buffer. Returns (chunk_to_send, remainder).
    Words are split by spaces; we never break mid-word.
    """
    parts = buffer.split()
    if len(parts) <= n:
        return ("", buffer)
    send = " ".join(parts[:n]) + " "
    remainder = " ".join(parts[n:])
    return (send, remainder)


async def _stream_word_grouped_sse(
    history: list[dict],
    message: str,
    on_stream_done: Callable[[str], Awaitable[int]],
) -> AsyncGenerator[str, None]:
    """
    Async generator: consume Gemini chunks from a queue, buffer, send every
    STREAM_WORD_GROUP_SIZE words with STREAM_DELAY_MS between sends.
    Flushes remainder when stream ends, then calls on_stream_done(full_reply)
    and yields done event.
    """
    settings = get_settings()
    group_size = max(1, settings.stream_word_group_size)
    delay_s = max(0.0, settings.stream_delay_ms / 1000.0)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    executor = None  # use default thread pool
    producer_future = loop.run_in_executor(
        executor,
        _sync_producer,
        history,
        message,
        queue,
        loop,
    )

    buffer = ""
    full_reply: list[str] = []

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                await asyncio.sleep(0)
                continue
            if item is None:
                break
            if isinstance(item, Exception):
                yield _sse_message({"error": "AI service temporarily unavailable."})
                return
            buffer += item
            full_reply.append(item)
            # Group by words: send when we have >= group_size words
            while True:
                chunk, remainder = _take_words(buffer, group_size)
                if not chunk:
                    buffer = remainder
                    break
                buffer = remainder
                yield _sse_message({"delta": chunk})
                await asyncio.sleep(delay_s)

        # Flush remaining buffer (whole words only; no mid-word break, no extra trailing space)
        if buffer.strip():
            yield _sse_message({"delta": buffer})

    finally:
        await producer_future

    full_text = "".join(full_reply)
    try:
        remaining = await on_stream_done(full_text)
    except Exception as e:
        logger.warning("on_stream_done failed (stream continues): %s", e)
        remaining = 0
    yield _sse_message({"done": True, "remaining_today": remaining})


async def stream_chat_response(
    history: list[dict],
    message: str,
    on_stream_done: Callable[[str], Awaitable[int]],
) -> StreamingResponse:
    """
    Build a StreamingResponse with word-grouped, delayed SSE for a natural feel.
    on_stream_done(full_reply_text) is called after the stream ends; it should
    save the turn, log usage, and return remaining_today. If it raises, we log
    and send remaining_today=0 in the done event.
    """
    return StreamingResponse(
        _stream_word_grouped_sse(history, message, on_stream_done),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
