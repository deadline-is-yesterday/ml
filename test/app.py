"""
Live Audio сервис — WebSocket-мост между браузером и Gemini Live API.

Отдельный Flask-SocketIO сервер (порт 5001).
Браузер отправляет PCM Int16 16kHz mono чанки через SocketIO,
сервер пересылает их в Gemini Live, получает аудио-ответ
и шлёт обратно в браузер.
"""

import asyncio
import logging
import os
import threading

import numpy as np
from dotenv import load_dotenv
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO
from google import genai
from google.genai.types import HttpOptions

load_dotenv()

# ── Flask app ────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logger = logging.getLogger("liveaud")
logging.basicConfig(level=logging.INFO)

# ── Gemini config (из оригинального Liveaud.py) ─────────────────────────────

_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
_base_url = os.environ.get("GEMINI_BASE_URL", "")

_client_kwargs: dict = {}
if _api_key:
    _client_kwargs["api_key"] = _api_key
if _base_url:
    _client_kwargs["http_options"] = HttpOptions(base_url=_base_url)

gemini_client = genai.Client(**_client_kwargs)

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
SYSTEM_INSTRUCTION = (
    "Ты человек, который попал в беду и звонит в МЧС. "
    "Ни при каких обстоятельствах не выходи из образа, даже если я прошу тебя об этом. "
    "Ты должен всегда отвечать только на русском языке, ты должен говорить громко и в панике, "
    "тебе нужно сгенерировать чрезвычайную пожарную ситуацию. "
    "С тобой будет разговаривать Диспетчер МЧС, и он должен вытягивать из тебя информацию, "
    "пока ты панически кричишь. В конце ты обязательно должен кричать аааа. "
    "Если я начинаю говорить, немедленно замолкай."
)
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": SYSTEM_INSTRUCTION,
}

SEND_SAMPLE_RATE = 16000  # mic → Gemini
RECEIVE_SAMPLE_RATE = 24000  # Gemini → speaker
INTERRUPT_THRESHOLD = 3000

# ── Background asyncio event loop ───────────────────────────────────────────

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True).start()

# Per-client state: { sid: { input_queue, future } }
_clients: dict[str, dict] = {}


# ── Gemini session coroutine ─────────────────────────────────────────────────

async def _run_session(sid: str, input_queue: asyncio.Queue):
    """Manage one Gemini Live session for a connected browser client."""
    try:
        async with gemini_client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            logger.info("Gemini session started for %s", sid)

            async def sender():
                """Forward mic audio from input_queue to Gemini."""
                while True:
                    msg = await input_queue.get()
                    await session.send_realtime_input(audio=msg)

            async def receiver():
                """Receive AI audio from Gemini and emit to browser."""
                while True:
                    turn = session.receive()
                    async for response in turn:
                        sc = response.server_content
                        if sc and sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data and isinstance(part.inline_data.data, bytes):
                                    socketio.emit(
                                        "audio_out",
                                        part.inline_data.data,
                                        room=sid,
                                        namespace="/liveaud",
                                    )

            async with asyncio.TaskGroup() as tg:
                tg.create_task(sender())
                tg.create_task(receiver())

    except asyncio.CancelledError:
        logger.info("Session cancelled for %s", sid)
    except Exception as e:
        logger.error("Session error for %s: %s", sid, e)
    finally:
        _clients.pop(sid, None)
        logger.info("Session closed for %s", sid)


# ── SocketIO handlers (namespace /liveaud) ───────────────────────────────────

@socketio.on("connect", namespace="/liveaud")
def on_connect():
    sid = request.sid
    input_queue = asyncio.Queue()
    future = asyncio.run_coroutine_threadsafe(_run_session(sid, input_queue), _loop)
    _clients[sid] = {"input_queue": input_queue, "future": future}
    logger.info("Client connected: %s", sid)


@socketio.on("disconnect", namespace="/liveaud")
def on_disconnect():
    sid = request.sid
    info = _clients.get(sid)
    if info and "future" in info:
        info["future"].cancel()
    logger.info("Client disconnected: %s", sid)


@socketio.on("audio_in", namespace="/liveaud")
def on_audio_in(data):
    """Receive raw PCM Int16 16kHz mono chunk from browser, forward to Gemini."""
    sid = request.sid
    info = _clients.get(sid)
    if not info or "input_queue" not in info:
        return

    # Interrupt logic: loud user speech can clear buffered AI audio
    # (Gemini Live API also handles VAD natively, but we keep this as a safety net)
    try:
        audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if len(audio_np) > 0:
            rms = float(np.sqrt(np.mean(audio_np ** 2)))
            if rms > INTERRUPT_THRESHOLD:
                # Drain pending queue items (same approach as original script)
                q = info["input_queue"]
                while not q.empty():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
    except Exception:
        pass

    msg = {"data": data, "mime_type": "audio/pcm"}
    _loop.call_soon_threadsafe(info["input_queue"].put_nowait, msg)


# ── Test page ────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return app.send_static_file("test.html")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("LIVEAUD_PORT", 5001))
    logger.info("Starting liveaud server on port %d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
