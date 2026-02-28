import asyncio
from google import genai
import pyaudio
import dotenv

dotenv.load_dotenv()

client = genai.Client(
    # http_options={
    #     "base_url": "https://flask-python-boilerplate-ten-gamma.vercel.app"
    # }
)

# --- pyaudio config ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

# --- Live API config ---
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": "Ты человек, который попал в беду и звонит в МЧС. Ты должен всегда отвечать только на русском языке, ты должен говорить громко и в панике, тебе нужно сгенерировать чрезвычайную пожарную ситуацию. С тобой будет разговаривать Диспетчер МЧС, и он должен вытягивать из тебя информацию, пока ты панически кричишь. В конце ты обязательно должен кричать аааа",
}

audio_queue_output = asyncio.Queue()
audio_queue_mic = asyncio.Queue(maxsize=5)
audio_stream = None

async def listen_audio():
    """Listens for audio and puts it into the mic audio queue."""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    kwargs = {"exception_on_overflow": False} if __debug__ else {}
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
        await audio_queue_mic.put({"data": data, "mime_type": "audio/pcm"})

async def send_realtime(session):
    """Sends audio from the mic audio queue to the GenAI session."""
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)


async def receive_audio(session):
    """Receives responses from GenAI and puts audio data into the speaker audio queue."""
    while True:
        turn = session.receive()

        # Получаем кусочки аудио от сервера
        async for response in turn:
            if (response.server_content and response.server_content.model_turn):
                for part in response.server_content.model_turn.parts:
                    if part.inline_data and isinstance(part.inline_data.data, bytes):
                        # Кладем полезный звук в очередь на воспроизведение
                        audio_queue_output.put_nowait(part.inline_data.data)

        # --- ИСПРАВЛЕНИЕ ---
        # Сюда мы попадаем, когда сервер закончил передавать текущий ответ.
        # Чтобы PyAudio точно проиграл последние миллисекунды фразы и не "зажевал" их в буфере,
        # мы искусственно добавляем полсекунды абсолютной тишины.
        # Частота 24000 Гц * 2 байта (16-бит) / 2 (полсекунды) = 24000 байт нулей.
        silence = b'\x00' * 24000
        audio_queue_output.put_nowait(silence)

        # Обратите внимание: старый код очистки очереди (while not audio_queue_output.empty())
        # отсюда полностью удален!

async def play_audio():
    """Plays audio from the speaker audio queue."""
    stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
    )
    while True:
        bytestream = await audio_queue_output.get()
        await asyncio.to_thread(stream.write, bytestream)

async def run():
    """Main function to run the audio loop."""
    try:
        async with client.aio.live.connect(
            model=MODEL, config=CONFIG
        ) as live_session:
            print("Connected to Gemini. Start speaking!")
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_realtime(live_session))
                tg.create_task(listen_audio())
                tg.create_task(receive_audio(live_session))
                tg.create_task(play_audio())
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\nConnection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Interrupted by user.")