# 🎙️ Friday — Local Voice AI Assistant for Windows

A fully functional **offline-first** voice AI assistant for **Windows 10/11** that handles daily operations through natural voice commands.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎙️ **Offline Speech Recognition** | Converts speech to text using **Vosk** (no internet required) |
| 🔊 **Text-to-Speech** | Natural voice responses via **pyttsx3** (fully offline) |
| 💻 **App Launcher** | Open any Windows application by name |
| ⏰ **Alarms & Reminders** | Schedule alarms and reminders with Windows toast notifications |
| 📩 **WhatsApp Messaging** | Send WhatsApp messages via **pywhatkit** |
| 📧 **Email** | Send emails via Gmail (SMTP + App Password) |
| 🧠 **Natural Language Understanding** | Regex + keyword intent parsing |

---

## 📋 Prerequisites

- **Python 3.8+**
- **Windows 10 or Windows 11**
- A working **microphone**
- (For email) A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)
- (For WhatsApp) WhatsApp Web logged in on the default browser

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/VatsAditya48/voice-assistant.git
cd voice-assistant
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

> **PyAudio on Windows**: If `pip install pyaudio` fails, download the pre-built wheel from
> [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio) and install it with:
> ```bash
> pip install PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl
> ```

### 3. Download the Vosk model (automatic)

The assistant automatically downloads the small English model
(`vosk-model-small-en-us-0.15`, ~40 MB) on first run.  
To pre-download manually:

```bash
# The model is saved to models/vosk-model-small-en-us-0.15/
python -c "from assistant.listener import _download_model; _download_model('models/vosk-model-small-en-us-0.15')"
```

---

## ⚙️ Configuration

### `config/settings.yaml`

```yaml
assistant:
  name: "Friday"
  wake_word: "hey friday"

voice:
  rate: 175        # words per minute
  volume: 1.0      # 0.0 – 1.0
  voice_id: 0      # 0 = male, 1 = female

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "your_email@gmail.com"
  sender_password: "your_app_password"   # Gmail App Password

whatsapp_contacts:
  John: "+1234567890"
  Mom: "+0987654321"

vosk:
  model_path: "models/vosk-model-small-en-us-0.15"
```

### `config/apps.yaml`

Maps spoken app names to their Windows executable paths.  
Pre-configured for common apps; add custom entries as needed:

```yaml
chrome: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
notepad: "notepad.exe"
vscode: "C:\\Users\\%USERNAME%\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"
```

---

## ▶️ Usage

```bash
python main.py
```

Say the **wake word** (default: *"hey friday"*) and then speak your command.

### 💬 Example Voice Commands

| Command | Description |
|---|---|
| *"Hey Friday, open Chrome"* | Launch Google Chrome |
| *"Hey Friday, open Notepad"* | Launch Notepad |
| *"Hey Friday, set alarm for 7:30 AM"* | Set an alarm |
| *"Hey Friday, wake me up at 6 AM"* | Set an alarm |
| *"Hey Friday, remind me to call Mom at 5 PM"* | Set a reminder |
| *"Hey Friday, remind me to take medicine in 30 minutes"* | Relative reminder |
| *"Hey Friday, what time is it?"* | Get the current time |
| *"Hey Friday, what's today's date?"* | Get today's date |
| *"Hey Friday, send WhatsApp message to John saying I'll be late"* | Send WhatsApp |
| *"Hey Friday, send email to john@example.com subject Meeting body See you at 3"* | Send email |
| *"Hey Friday, list alarms"* | Show scheduled alarms/reminders |
| *"Hey Friday, exit"* | Shut down the assistant |

---

## 🏗️ Project Structure

```
voice-assistant/
├── main.py                  # Entry point — main listening loop
├── assistant/
│   ├── __init__.py
│   ├── listener.py          # Microphone → text (Vosk STT)
│   ├── speaker.py           # Text → voice (pyttsx3 TTS)
│   ├── intent_parser.py     # Parse commands into intents & entities
│   ├── app_launcher.py      # Open Windows applications
│   ├── scheduler.py         # Alarms & reminders (APScheduler + win10toast)
│   └── messenger.py         # Email (smtplib) & WhatsApp (pywhatkit)
├── config/
│   ├── settings.yaml        # User preferences & credentials
│   └── apps.yaml            # App name → executable path mappings
├── requirements.txt
├── setup.py
└── tests/
    ├── test_intent_parser.py
    ├── test_app_launcher.py
    ├── test_scheduler.py
    └── test_messenger.py
```

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 🛠️ Troubleshooting

### Microphone not detected
- Ensure your microphone is set as the **default recording device** in Windows Sound settings.
- Try running as Administrator.

### PyAudio installation fails
- Use a pre-built wheel — see [Installation](#installation).
- Alternatively, install via Conda: `conda install pyaudio`.

### Vosk model not downloading
- Check your internet connection; the model is ~40 MB.
- Download manually from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) and extract to `models/`.

### WhatsApp messages not sending
- Make sure **WhatsApp Web** is already logged in on your default browser.
- `pywhatkit` opens a browser tab; keep it open until the message is sent.

### Email authentication fails
- Use a **Gmail App Password** (not your regular password).
  1. Enable 2-Step Verification on your Google account.
  2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and create a password.
  3. Use that 16-character password in `settings.yaml`.

### Windows toast notifications not appearing
- Ensure `win10toast` is installed: `pip install win10toast`.
- Notifications require Windows 10 or later.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
