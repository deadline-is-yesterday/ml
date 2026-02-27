from vosk import Model, KaldiRecognizer
import speech_recognition
import wave
import json
import os
import pyaudio  # Новое: для ручной записи звука
import time  # Новое: для пауз в цикле
from pynput import keyboard  # Новое: для отслеживания Пробела

# Глобальный флаг-переключатель
is_recording = False


def on_press(key):
    """Слушает клавиатуру в фоне. Пробел работает как переключатель Вкл/Выкл."""
    global is_recording
    try:
        if key == keyboard.Key.space:
            is_recording = not is_recording  # Меняем состояние на противоположное
    except AttributeError:
        pass


def record_and_recognize_audio(*args: tuple):
    """
    Запись (пока is_recording == True) и последующее распознавание аудио.
    """
    global is_recording
    recognized_data = ""

    # --- ЧАСТЬ 1: ЗАПИСЬ ЗВУКА ДО ПОВТОРНОГО НАЖАТИЯ ---
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    print("\nListening... (Нажми ПРОБЕЛ еще раз, чтобы остановить запись)")
    frames = []

    # Пишем звук, пока флаг включен
    while is_recording:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Сохраняем в файл, как и было в твоем старом коде
    with wave.open("microphone-results.wav", 'wb') as file:
        file.setnchannels(CHANNELS)
        file.setsampwidth(p.get_sample_size(FORMAT))
        file.setframerate(RATE)
        file.writeframes(b''.join(frames))

    # Считываем готовый файл для библиотеки speech_recognition
    with speech_recognition.AudioFile("microphone-results.wav") as source:
        audio = recognizer.record(source)

    # --- ЧАСТЬ 2: ТВОЙ СТАРЫЙ БЛОК РАСПОЗНАВАНИЯ (БЕЗ ИЗМЕНЕНИЙ) ---
    try:
        print("Started recognition...")
        recognized_data = recognizer.recognize_google(audio, language="ru").lower()

    except speech_recognition.UnknownValueError:
        pass

    except speech_recognition.RequestError:
        print("Trying to use offline recognition...")
        recognized_data = use_offline_recognition()

    return recognized_data


def use_offline_recognition():
    """
    Переключение на оффлайн-распознавание речи (Функция оставлена без изменений)
    """
    recognized_data = ""
    try:
        if not os.path.exists("models/vosk-model-small-ru-0.4"):
            print("Please download the model from:\n"
                  "https://alphacephei.com/vosk/models and unpack as 'model' in the current folder.")
            exit(1)

        wave_audio_file = wave.open("microphone-results.wav", "rb")
        model = Model("models/vosk-model-small-ru-0.4")
        offline_recognizer = KaldiRecognizer(model, wave_audio_file.getframerate())

        data = wave_audio_file.readframes(wave_audio_file.getnframes())
        if len(data) > 0:
            if offline_recognizer.AcceptWaveform(data):
                recognized_data = offline_recognizer.Result()
                recognized_data = json.loads(recognized_data)
                recognized_data = recognized_data["text"]
    except:
        print("Sorry, speech service is unavailable. Try again later")

    return recognized_data


if __name__ == "__main__":
    # Запускаем фоновый слушатель клавиатуры
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    # Инициализация (микрофон больше не нужен, мы читаем напрямую через PyAudio)
    recognizer = speech_recognition.Recognizer()

    print("✅ Система готова. Нажми ПРОБЕЛ для начала записи.")

    while True:
        # Ждем, пока пользователь нажмет Пробел (is_recording станет True)
        if is_recording:
            # Функция сама запишет звук, остановится по второму пробелу и вернет текст
            voice_input = record_and_recognize_audio()

            # Удаляем временный файл
            if os.path.exists("microphone-results.wav"):
                os.remove("microphone-results.wav")

            if voice_input:
                print(f"Распознано: {voice_input}")
            else:
                print("Речь не распознана.")

            print("\nНажми ПРОБЕЛ для новой записи...")

        # Небольшая пауза для разгрузки процессора
        time.sleep(0.05)