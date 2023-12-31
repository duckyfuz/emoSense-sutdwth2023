import threading
import tkinter as tk
import numpy as np
import soundfile as sf
import sounddevice as sd
from scipy.io.wavfile import write
import pyaudio
import wave
import audioop
import speech_recognition as sr
from pydub import AudioSegment
import os
import openai
from gtts import gTTS
import pygame
import constant
import emoji
import time

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Function to record audio to a WAV file using sounddevice


def record_audio_to_wav(filename):
    fs = 44100  # Sample rate
    seconds = 3  # Duration of recording

    print("Recording...")

    myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
    sd.wait()  # Wait until recording is finished

    print("Recording finished.")

    wav_filename = filename + ".wav"
    write(wav_filename, fs, myrecording)  # Save as WAV file

    print(f"Saved recording as {wav_filename}")

# Function to record audio based on silence using pyaudio


def record_voice(thresh=constant.THRESH, max_silence=constant.MAX_SILENCE, filename="voice.wav"):
    p = pyaudio.PyAudio()  # Initialize pyaudio

    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    input=True,
                    frames_per_buffer=1024)  # Start the audio stream

    frame_count = 0
    frames = []
    is_recording = False

    print("Waiting for a noise to start recording...")

    while True:
        chunk = stream.read(1024)  # Read a chunk from audio input
        rms = audioop.rms(chunk, 2)  # Check for voice
        if rms > thresh:
            app.message.set("🗣️")  # Set an hourglass emoji
            app.additional_message.set('Recording...')  # Set the message
            if not is_recording:
                print("Noise detected, starting recording!")
                is_recording = True
                app.show_stop_button() 
            print("Detected voice!")
            frame_count = 0
        else:
            app.message.set("🗣️")  # Set an hourglass emoji
            app.additional_message.set(
                'No voice detected...')  # Set the message
            if is_recording:
                print("No voice detected.")
                frame_count += 1
        if is_recording:
            frames.append(chunk)
        if frame_count > max_silence and is_recording:
            print("Max silence reached, stopping.")
            app.stop_button.pack_forget()
            break
        if app.stop_recording_flag:  # Check the flag here
            print("Stop button pressed, stopping.")
            app.stop_button.pack_forget()
            time.sleep(1)
            app.stop_recording_flag = False  # Reset the flag
            break

    stream.stop_stream()
    stream.close()
    p.terminate()

    if frames:
        wf = wave.open(filename, 'wb')  # Save audio to file
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b''.join(frames))
        wf.close()

# Function to convert audio to text using Google Web Speech API


def audio_to_text(audio_file_path):
    recognizer = sr.Recognizer()

    audio = AudioSegment.from_file(audio_file_path, format="wav")
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export("temp.wav", format="wav")

    with sr.AudioFile("temp.wav") as source:
        audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data)
            return text, len(text.split())
        except sr.UnknownValueError:
            return False, 4
        except sr.RequestError as e:
            return f"Could not request results from Google Web Speech API; {e}", 4

# Function to classify emotion from text using OpenAI GPT-3


def textToEmotion(text):

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": app.system_message},
            {"role": "user", "content": text}
        ]
    )

    emotion = completion.choices[0].message.content
    print(emotion)
    return emotion

# Function to play text as audio using Google Text-to-Speech (gTTS) and pygame


def play_text_as_audio(text, language='en'):
    tts = gTTS(text=text, lang=language)
    tts.save("temp.mp3")

    pygame.mixer.init()
    pygame.mixer.music.load("temp.mp3")
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

# Function to get loudness and duration of an audio file


def get_loudness(file_path):
    data, sample_rate = sf.read(file_path)
    rms = (data**2).mean()**0.5
    loudness = 20 * np.log10(rms)
    duration = len(data) / sample_rate
    return loudness, duration

# Class for the GUI application

class MessageApp:
    def __init__(self, root):
        self.root = root
        self.root.title("emoSense")
        self.root.configure(bg="white")

        self.stop_recording_flag = False  
        self.stop_button = tk.Button(root, text="Stop Recording", command=self.stop_recording, bg='red')

        self.message = tk.StringVar()
        self.message_label = tk.Label(
            root, textvariable=self.message, font=("Helvetica", 320), fg="black", bg='white', borderwidth=0, highlightthickness=0)
        self.message_label.pack(padx=20, pady=20)

        self.additional_message = tk.StringVar()
        self.additional_message_label = tk.Label(
            root, textvariable=self.additional_message, font=("Helvetica", 24), fg="black", bg='white', borderwidth=0, highlightthickness=0)
        self.additional_message_label.pack(
            padx=20, pady=10)  # Adjust padding as needed

        self.system_message = ""
        self.show_system_message_dialog()
        # self.start_button = tk.Button(
        #     root, text="Start", command=self.start_processing, bg='blue')
        # self.start_button.pack()
        self.start_processing()

    def start_processing(self):
        # Disable the button after it's pressed
        # self.start_button.config(state="disabled")

        processing_thread = threading.Thread(target=self.process_loop)
        processing_thread.start()
        # self.process_loop()

    def show_system_message_dialog(self):
        self.system_message_var = tk.StringVar(value="A")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Select System Message")
        
        tk.Label(dialog, text="Select an option:").pack()
        
        tk.Radiobutton(dialog, text="Low Functioning", variable=self.system_message_var, value="low").pack()
        tk.Radiobutton(dialog, text="High Functioning", variable=self.system_message_var, value="high").pack()
        
        tk.Button(dialog, text="OK", command=lambda: self.set_system_message_and_destroy_dialog(dialog)).pack()
    
    def set_system_message_and_destroy_dialog(self, dialog):
        selected_option = self.system_message_var.get()
        
        if selected_option == "low":
            self.system_message = constant.SYSTEM_MESSAGE1
        elif selected_option == "high":
            self.system_message = constant.SYSTEM_MESSAGE2
        
        dialog.destroy()

    def process_loop(self):
        record_voice()

        audio_file_path = "voice.wav"

        self.root.configure(bg='green')
        self.message_label.config(bg='green')
        self.additional_message_label.config(bg='green')
        self.message.set(emoji.emojize("\U000023F3"))  # Set an hourglass emoji
        self.additional_message.set('Loading...')  # Set the message

        loudness, duration = get_loudness(audio_file_path)
        text, length = audio_to_text(audio_file_path)
        speed = "fast" if length / \
            duration > 3 else "normal" if length / duration > 2 else "slow"
        loud = "loud" if loudness > -20 else "normal" if loudness > -30 else "soft"

        if text != False:
            print(f"Average Loudness: {loudness}")
            print(
                f"Transcribed text: {text}, Speed: {speed}, Loudness: {loud}")

            emotion = textToEmotion(
                "Sentence: " + text + "\nSpeed: " + speed + "\Loudness: " + loud)

            print(f"Emotion: {emotion}")

            # Update the displayed emoji
            self.message.set(emoji.emojize(self.get_emotion_emoji(emotion)))
            self.additional_message.set(text)  # Set an hourglass emoji

            # Set background color and text color based on emotion
            self.update_text_color(emotion)
            self.root.configure(bg=self.get_emotion_color(emotion))
            self.message_label.config(bg=self.get_emotion_color(emotion))
            self.additional_message_label.config(
                bg=self.get_emotion_color(emotion))

            play_text_as_audio(emotion)

        else:
            self.message.set("❌")
            self.additional_message.set(
                'Could not detect voice. Try again.')  # Set the message

        time.sleep(2)

        processing_thread = threading.Thread(target=self.process_loop)
        processing_thread.start()

        # Schedule next iteration
        self.root.after(1000, processing_thread.start)

    def get_emotion_emoji(self, emotion):
        emojis = {
            "anger": "\U0001F620",       # 😠
            "disgust": "\U0001F922",     # 🤢
            "fear": "\U0001F628",        # 😨
            "joy": "\U0001F604",         # 😀
            "sadness": "\U0001F614",     # 😔
            "surprise": "\U0001F632",    # 😲
            "neutral": "\U0001F610" ,     # 😐
            "mad": "\U0001F621",         # 😡
            "distant": "\U0001F636",     # 😶
            "disappointed": "\U0001F61E",  # 😞
            "repulsed": "\U0001F616",    # 😖
            "hurt": "\U0001F915",        # 🤕
            "despair": "\U0001F62D",     # 😭
            "optimistic": "\U0001F60A",  # 😊
            "playful": "\U0001F61C",     # 😜
            "startled": "\U0001F631",    # 😱
            "excited": "\U0001F929",     # 🤩
            "bored": "\U0001F634",       # 😴
            "stressed": "\U0001F62C",    # 😬
            "scared": "\U0001F628",      # 😨
            "insecure": "\U0001F641",    # 🙁
        }
        # Return the appropriate emoji or a question mark emoji
        return emojis.get(emotion, ":question:")

    def stop_recording(self):
        self.stop_recording_flag = True

    def show_stop_button(self):
        self.stop_button.pack()

    def update_text_color(self, emotion):
        if emotion in ['anger', 'disgust', 'fear']:
            # Set text color to white for dark backgrounds
            self.message_label.config(fg='white')
            self.additional_message_label.config(fg='white')
        else:
            # Set text color to black for light backgrounds
            self.message_label.config(fg='black')
            self.additional_message_label.config(fg='white')

    def get_emotion_color(self, emotion):
        colors = {
            "anger": "red",
            "disgust": "purple",
            "fear": "darkorange",
            "joy": "yellow",
            "sadness": "blue",
            "surprise": "pink",
            "neutral": "white",
            "mad": "darkred",
            "distant": "grey",
            "disappointed": "slategray",
            "repulsed": "green",
            "hurt": "brown",
            "despair": "navy",
            "optimistic": "lightyellow",
            "playful": "lightpink",
            "startled": "orange",
            "excited": "gold",
            "bored": "lightgrey",
            "stressed": "black",
            "scared": "darkorange",
            "insecure": "darkgrey"
        }

        # Get the emotion color or default to white
        return colors.get(emotion, "white")

if __name__ == "__main__":
    root = tk.Tk()
    app = MessageApp(root)
    root.mainloop()
