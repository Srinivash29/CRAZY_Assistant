
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QLineEdit, QPushButton
)

# Load the secret key from this project's .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL_NAME = "openai/gpt-oss-120b"


class AIWorker(QThread):
    # Signals send results safely back to the GUI
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):
        try:
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

        except Exception as error:
            # Show a useful error without exposing the API key
            print("Groq error:", type(error).__name__, str(error))
            self.error_occurred.emit(
                f"AI request failed ({type(error).__name__}). "
                "Check your internet, API key, model and account limits. "
                "See the VS Code terminal for details."
            )


class CrazyAssistant(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CRAZY AI Assistant")
        self.setMinimumSize(800, 550)

        self.history = [
            {
                "role": "system",
                "content": (
                    "You are CRAZY, a helpful personal AI assistant. "
                    "Address the user as sir when natural. "
                    "Give clear, useful answers."
                )
            }
        ]

        self.worker = None
        self.busy = False

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
        self.chat.append("CRAZY: Groq AI connection is ready to test.")

        input_layout = QHBoxLayout()

        self.message = QLineEdit()
        self.message.setPlaceholderText("Ask CRAZY anything...")
        self.message.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("SEND")
        self.send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.message)
        input_layout.addWidget(self.send_button)

        self.status = QLabel("STATUS: READY | MODEL: GROQ")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.chat, 1)
        layout.addLayout(input_layout)
        layout.addWidget(self.status)

    def send_message(self):
        text = self.message.text().strip()

        if not text or self.busy:
            return

        if not os.getenv("GROQ_API_KEY"):
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

        self.busy = True
        self.send_button.setEnabled(False)
        self.message.setEnabled(False)
        self.status.setText("STATUS: CRAZY IS THINKING...")

        # Run network requests in a separate thread
        self.worker = AIWorker(list(self.history))
        self.worker.response_ready.connect(self.on_response)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_response(self, answer):
        self.history.append({
            "role": "assistant",
            "content": answer
        })
        self.chat.append(f"CRAZY: {answer}")

    def on_error(self, message):
        # Remove the unanswered user message from model history
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()

        self.chat.append(f"CRAZY: {message}")
        self.status.setText("STATUS: REQUEST FAILED")

    def on_finished(self):
        self.busy = False
        self.send_button.setEnabled(True)
        self.message.setEnabled(True)
        self.message.setFocus()

        if self.status.text() != "STATUS: REQUEST FAILED":
            self.status.setText("STATUS: READY | MODEL: GROQ")

        self.worker = None

    def closeEvent(self, event):
        # Avoid closing the window while its worker is active
        if self.worker is not None and self.worker.isRunning():
            self.chat.append(
                "CRAZY: Please wait for the current request to finish."
            )
            event.ignore()
            return

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CrazyAssistant()
    window.show()

    sys.exit(app.exec())
