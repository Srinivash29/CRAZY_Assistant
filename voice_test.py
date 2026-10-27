
import speech_recognition as sr
import pyttsx3


def main():
    # Test text-to-speech
    speaker = pyttsx3.init()
    speaker.setProperty("rate", 170)

    print("Testing speaker...")
    speaker.say("Hello sir. CRAZY voice test is working.")
    speaker.runAndWait()

    # Test microphone
    recognizer = sr.Recognizer()

    print("\nAvailable microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"{index}: {name}")

    print("\nStarting microphone test...")
    print("Speak a short sentence after the prompt.")

    try:
        with sr.Microphone(
            device_index=1,
            sample_rate=44100
        ) as source:
            recognizer.adjust_for_ambient_noise(
                source, duration=1
            )
            print("Listening...")
            audio = recognizer.listen(
                source, timeout=8, phrase_time_limit=8
            )

        print("Recognizing speech...")
        text = recognizer.recognize_google(audio)
        print("Recognized:", text)

        speaker.say("Sir, I heard you say: " + text)
        speaker.runAndWait()

    except sr.WaitTimeoutError:
        print("No speech detected before timeout.")

    except sr.UnknownValueError:
        print("Speech was detected, but could not be understood.")

    except sr.RequestError as error:
        print("Speech recognition service error:", error)

    except Exception as error:
        print("Voice test failed:", type(error).__name__, error)


if __name__ == "__main__":
    main()
