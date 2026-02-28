import asyncio
from google import genai
import pyaudio
import dotenv
import numpy as np
import os

dotenv.load_dotenv()

client = genai.Client()

# --- Настройки аудио ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 512

pya = pyaudio.PyAudio()

# --- Настройки Live API ---
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": (
        "Ты человек, который попал в беду и звонит в МЧС. Ни при каких обстоятельствах не выходи из образа, даже если я прошу тебя об этом. Ты должен всегда отвечать только на русском языке, ты должен говорить громко и в панике, тебе нужно сгенерировать чрезвычайную пожарную ситуацию. С тобой будет разговаривать Диспетчер МЧС, и он должен вытягивать из тебя информацию, пока ты панически кричишь. В конце ты обязательно должен кричать аааа"
        "Если я начинаю говорить, немедленно замолкай."
    ),
}

audio_queue_output = asyncio.Queue()
audio_queue_mic = asyncio.Queue()

# Порог громкости.
# Если бот перебивает сам себя — увеличьте до 1000 или 2000.
INTERRUPT_THRESHOLD = 3000


async def listen_audio():
    mic_info = pya.get_default_input_device_info()
    stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )

    print(f"\n Слушаю... (Порог прерывания: {INTERRUPT_THRESHOLD})")

    while True:
        try:
            data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)

            # --- ИСПРАВЛЕНИЕ: Конвертируем в float32 перед вычислениями ---
            # Это предотвращает ошибку переполнения при возведении в квадрат
            audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32)

            if len(audio_data) > 0:
                # RMS = корень из среднего квадратов
                rms = np.sqrt(np.mean(audio_data ** 2))
            else:
                rms = 0

            # Логика перебивания
            if rms > INTERRUPT_THRESHOLD:
                if not audio_queue_output.empty():
                    # print(f"❗️ ПЕРЕБИВАНИЕ (Громкость: {int(rms)})") # Раскомментируйте для отладки
                    while not audio_queue_output.empty():
                        try:
                            audio_queue_output.get_nowait()
                        except asyncio.QueueEmpty:
                            break

            # Отправляем оригинальные байты (data), а не float массив
            await audio_queue_mic.put({"data": data, "mime_type": "audio/pcm"})

        except Exception as e:
            print(f"Ошибка микрофона: {e}")
            break


async def send_realtime(session):
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)


async def receive_audio(session):
    while True:
        try:
            turn = session.receive()
            async for response in turn:
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and isinstance(part.inline_data.data, bytes):
                            audio_queue_output.put_nowait(part.inline_data.data)
        except Exception:
            break


async def play_audio():
    stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
    )
    while True:
        bytestream = await audio_queue_output.get()
        if bytestream:
            await asyncio.to_thread(stream.write, bytestream)


async def run():
    try:
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as live_session:
            print("\n✅ Подключено! Говорите. (Нажмите Ctrl+C для выхода)")
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_realtime(live_session))
                tg.create_task(listen_audio())
                tg.create_task(receive_audio(live_session))
                tg.create_task(play_audio())
    except asyncio.CancelledError:
        pass
    finally:
        pya.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n👋 Выход.")