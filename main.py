import speech_recognition as sr
import pyttsx3
import os
import sys
import json
import sqlite3
from datetime import datetime
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QLineEdit, QPushButton, QComboBox
)

# Load the secret key from this project's .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL_NAME = "openai/gpt-oss-120b"
LOCAL_MODEL_NAME = "qwen2.5:1.5b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"


class AIWorker(QThread):
    # Signals send results safely back to the GUI
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, messages, provider):
        super().__init__()
        self.messages = messages
        self.provider = provider

    def run(self):
        try:
            if self.provider == "LOCAL":
                payload = {
                    "model": LOCAL_MODEL_NAME,
                    "messages": self.messages,
                    "stream": False,
                    "options": {"temperature": 0.7}
                }
                request = urllib.request.Request(
                    OLLAMA_CHAT_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(request, timeout=180) as response:
                    result = json.loads(response.read().decode("utf-8"))
                answer = result.get("message", {}).get("content", "")
            else:
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    self.error_occurred.emit(
                        "API key missing. Check your .env file."
                    )
                    return

                client = Groq(api_key=api_key)
                result = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=self.messages,
                    temperature=0.7,
                    max_completion_tokens=1024,
                    timeout=60.0
                )
                answer = result.choices[0].message.content

            if answer:
                self.response_ready.emit(answer)
            else:
                self.error_occurred.emit(
                    "The AI returned an empty response."
                )

        except urllib.error.URLError as error:
            print("Ollama connection error:", type(error).__name__, str(error))
            self.error_occurred.emit(
                "Could not reach Ollama. Make sure Ollama is running "
                "and qwen2.5:1.5b is installed."
                if self.provider == "LOCAL"
                else "Could not connect to the AI service."
            )
        except Exception as error:
            print(f"{self.provider} AI error:", type(error).__name__, str(error))
            if self.provider == "LOCAL":
                self.error_occurred.emit(
                    f"Local AI request failed ({type(error).__name__}). "
                    "Check that Ollama is running and the model is installed."
                )
            else:
                self.error_occurred.emit(
                    f"AI request failed ({type(error).__name__}). "
                    "Check your internet, API key, model and account limits. "
                    "See the VS Code terminal for details."
                )

class VoiceInputWorker(QThread):
    recognized = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def run(self):
        try:
            recognizer = sr.Recognizer()

            with sr.Microphone(
                device_index=1,
                sample_rate=44100
            ) as source:
                self.status_changed.emit("STATUS: LISTENING...")
                recognizer.adjust_for_ambient_noise(
                    source, duration=0.5
                )
                audio = recognizer.listen(
                    source, timeout=8, phrase_time_limit=10
                )

            self.status_changed.emit("STATUS: RECOGNIZING SPEECH...")
            text = recognizer.recognize_google(audio)

            if text.strip():
                self.recognized.emit(text)
            else:
                self.error_occurred.emit(
                    "No speech was recognized."
                )

        except sr.WaitTimeoutError:
            self.error_occurred.emit(
                "No speech detected. Please try again."
            )
        except sr.UnknownValueError:
            self.error_occurred.emit(
                "Sorry, I couldn't understand your speech."
            )
        except Exception as error:
            self.error_occurred.emit(
                f"Voice input failed: {type(error).__name__}: {error}"
            )


class SpeechWorker(QThread):
    error_occurred = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(self.text)
            engine.runAndWait()
            engine.stop()
        except Exception as error:
            self.error_occurred.emit(
                f"Speech output failed: {type(error).__name__}"
            )
class CrazyAssistant(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CRAZY AI Assistant")
        self.setMinimumSize(800, 550)

        self.system_message = {
            "role": "system",
            "content": (
                "You are CRAZY, a helpful personal Windows AI assistant. "
                "Address the user as sir when natural. "
                "Give clear, useful answers."
            )
        }
        self.memory_db_path = BASE_DIR / "crazy_memory.db"
        self.initialize_memory()
        self.history = [self.system_message] + self.load_recent_messages(limit=40)

        self.worker = None
        self.busy = False
        self.voice_worker = None
        self.tts_worker = None

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0b1020;
                color: #e5f3ff;
                font-family: Segoe UI;
                font-size: 14px;
            }

            QLabel#title {
                color: #00d9ff;
                font-size: 28px;
                font-weight: bold;
            }

            QTextEdit, QLineEdit {
                background-color: #121b2e;
                border: 1px solid #174c68;
                border-radius: 8px;
                padding: 10px;
                color: white;
            }

            QPushButton {
                background-color: #007fba;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #00a6df;
            }

            QPushButton:disabled {
                background-color: #34465a;
                color: #aab7c4;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(15)

        title = QLabel("CRAZY")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("YOUR PERSONAL AI ASSISTANT")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        self.chat.append("CRAZY: System initialized successfully.")
        self.chat.append("CRAZY: Choose LOCAL or ONLINE mode below.")
        saved_messages = self.load_recent_messages(limit=40)
        if saved_messages:
            self.chat.append("--- Previous conversation history ---")
            for item in saved_messages:
                speaker = "You" if item["role"] == "user" else "CRAZY"
                self.chat.append(f"{speaker}: {item['content']}")
            self.chat.append("--- End of saved history ---")

        input_layout = QHBoxLayout()

        self.message = QLineEdit()
        self.message.setPlaceholderText("Ask CRAZY anything...")
        self.message.returnPressed.connect(self.send_message)

        self.provider_box = QComboBox()
        self.provider_box.addItems(["ONLINE - Groq", "LOCAL - Ollama"])
        self.provider_box.currentIndexChanged.connect(self.on_provider_changed)

        self.send_button = QPushButton("SEND")
        self.send_button.clicked.connect(self.send_message)

        self.listen_button = QPushButton("LISTEN")
        self.listen_button.clicked.connect(self.start_listening)

        input_layout.addWidget(self.message)
        input_layout.addWidget(self.provider_box)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.listen_button)

        self.status = QLabel("STATUS: READY | MODEL: GROQ")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.chat, 1)
        layout.addLayout(input_layout)
        layout.addWidget(self.status)

    def initialize_memory(self):
        """Create the local SQLite database for conversation memory."""
        with sqlite3.connect(self.memory_db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    provider TEXT NOT NULL
                )
                """
            )

    def load_recent_messages(self, limit=40):
        """Load recent messages in chronological order."""
        with sqlite3.connect(self.memory_db_path) as connection:
            rows = connection.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        rows.reverse()
        return [{"role": role, "content": content} for role, content in rows]

    def save_exchange(self, user_text, assistant_text, provider):
        """Save a completed user/assistant exchange locally."""
        timestamp = datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect(self.memory_db_path) as connection:
            connection.executemany(
                "INSERT INTO messages (timestamp, role, content, provider) VALUES (?, ?, ?, ?)",
                [
                    (timestamp, "user", user_text, provider),
                    (timestamp, "assistant", assistant_text, provider)
                ]
            )

    def current_provider(self):
        return "LOCAL" if self.provider_box.currentIndex() == 1 else "ONLINE"

    def on_provider_changed(self):
        if not self.busy:
            model = "OLLAMA" if self.current_provider() == "LOCAL" else "GROQ"
            self.status.setText(f"STATUS: READY | MODEL: {model}")

    def send_message(self):
        text = self.message.text().strip()

        if not text or self.busy:
            return

        provider = self.current_provider()
        if provider == "ONLINE" and not os.getenv("GROQ_API_KEY"):
            self.chat.append(
                "CRAZY: API key not found. Check your .env file."
            )
            self.status.setText("STATUS: API KEY MISSING")
            return

        self.chat.append(f"You: {text}")
        self.message.clear()

        # Include conversation history for contextual replies
        self.history.append({
            "role": "user",
            "content": text
        })
        self.pending_user_text = text
        self.pending_provider = provider

        self.busy = True
        self.send_button.setEnabled(False)
        self.message.setEnabled(False)
        self.provider_box.setEnabled(False)
        model_label = "OLLAMA" if provider == "LOCAL" else "GROQ"
        self.status.setText(f"STATUS: CRAZY IS THINKING | MODEL: {model_label}...")

        # Keep API calls in a worker thread so the GUI stays responsive.
        self.worker = AIWorker(list(self.history), provider)
        self.worker.response_ready.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_response(self, answer):
        self.history.append({
            "role": "assistant",
            "content": answer
        })
        self.save_exchange(
            getattr(self, "pending_user_text", ""),
            answer,
            getattr(self, "pending_provider", self.current_provider())
        )
        self.pending_user_text = ""
        self.chat.append(f"CRAZY: {answer}")

        self.status.setText("STATUS: CRAZY IS SPEAKING...")

        self.tts_worker = SpeechWorker(answer)
        self.tts_worker.error_occurred.connect(
            self.on_speech_error
        )
        self.tts_worker.finished.connect(
            self.on_speech_finished
        )
        self.tts_worker.start()

    def on_speech_error(self, message):
        self.chat.append(f"CRAZY: {message}")

    def on_speech_finished(self):
        self.tts_worker = None

        if not self.busy:
            model = "OLLAMA" if self.current_provider() == "LOCAL" else "GROQ"
            self.status.setText(f"STATUS: READY | MODEL: {model}")

    def on_error(self, message):
        # Remove the unanswered user message from model history
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()
        self.pending_user_text = ""

        self.chat.append(f"CRAZY: {message}")
        self.status.setText("STATUS: REQUEST FAILED")

    def on_finished(self):
        self.busy = False
        self.send_button.setEnabled(True)
        self.message.setEnabled(True)
        self.listen_button.setEnabled(True)
        self.provider_box.setEnabled(True)
        self.message.setFocus()

        if (
            self.tts_worker is not None
            and self.tts_worker.isRunning()
        ):
            self.status.setText("STATUS: CRAZY IS SPEAKING...")
        elif self.status.text() != "STATUS: REQUEST FAILED":
            model = "OLLAMA" if self.current_provider() == "LOCAL" else "GROQ"
            self.status.setText(f"STATUS: READY | MODEL: {model}")

        self.worker = None

    def closeEvent(self, event):
        workers = [
            self.worker,
            self.voice_worker,
            self.tts_worker
        ]

        if any(
            worker is not None and worker.isRunning()
            for worker in workers
        ):
            self.chat.append(
                "CRAZY: Please wait for the current task to finish."
            )
            event.ignore()
            return

        event.accept()
    def start_listening(self):
        if self.busy:
            return

        if (
            self.voice_worker is not None
            and self.voice_worker.isRunning()
        ):
            return

        self.listen_button.setEnabled(False)
        self.send_button.setEnabled(False)
        self.message.setEnabled(False)

        self.voice_worker = VoiceInputWorker()
        self.voice_worker.status_changed.connect(
            self.status.setText
        )
        self.voice_worker.recognized.connect(
            self.on_voice_recognized
        )
        self.voice_worker.error_occurred.connect(
            self.on_voice_error
        )
        self.voice_worker.finished.connect(
            self.on_voice_finished
        )
        self.voice_worker.start()

    def on_voice_recognized(self, text):
        self.chat.append(f"You (voice): {text}")
        self.message.setText(text)
        self.send_message()

    def on_voice_error(self, message):
        self.chat.append(f"CRAZY: {message}")
        self.status.setText("STATUS: VOICE INPUT FAILED")

    def on_voice_finished(self):
        self.voice_worker = None
        self.listen_button.setEnabled(True)

        if not self.busy:
            self.send_button.setEnabled(True)
            self.message.setEnabled(True)

            if self.status.text() != "STATUS: VOICE INPUT FAILED":
                model = "OLLAMA" if self.current_provider() == "LOCAL" else "GROQ"
                self.status.setText(f"STATUS: READY | MODEL: {model}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CrazyAssistant()
    window.show()

    sys.exit(app.exec())
