# SYOS SPACE — Dynamic Face Recognition

**Academic prototype | Python · Computer Vision · Voice Interaction**

[Português](README.pt-BR.md)

SYOS SPACE (original project folder: `robo_visao2`) is a desktop computer vision prototype developed during a Computer Engineering internship in 2026 at Universidade CEUMA, São Luís, Brazil. It integrates real-time webcam face detection, recognition against locally enrolled facial representations, voice-guided enrollment and spoken greetings. It was designed as a basis for potential future integration with the Unitree Edu robot; the present release is a standalone desktop application, not a robot-control module.

## Features

- Webcam display with Tkinter and OpenCV; MediaPipe Face Mesh processes up to three faces.
- FaceNet512 embeddings via DeepFace, compared with cosine distance (configured threshold: 0.30).
- Green box for an unknown face; blue box and name for a recognized face.
- After approximately three seconds of an unknown face, the system initiates a Portuguese voice dialogue.
- Voice enrollment with five guided captures (center, right, left, down and up).
- Local SQLite storage of the name, reference image and averaged embedding, plus JPEG captures on disk.
- Spoken greetings with a ten-minute per-person cooldown; background processing using threads and queues.

## Requirements

Recommended starting environment: Python 3.11 (64-bit), Windows 10/11, webcam, microphone, speakers and internet access. Other desktop operating systems may work but require additional audio/Tkinter setup and have not been validated. Internet is needed for Google speech recognition and may be needed for the first download of pretrained model weights. No dedicated robot is required.

## Installation (Windows PowerShell)

Download or clone this repository, open a terminal in the directory containing `app.py`, then run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe app.py
```

The database (`rostos.db`) is created automatically. No pretrained weights or personal enrollment records are shipped. The requirements file is a suggested compatibility baseline, not a lockfile recovered from the original development machine; installation and live operation must be tested on the target computer. The original code requires the legacy `mp.solutions.face_mesh` API, which is why an older MediaPipe version is specified. DeepFace and MediaPipe declare different OpenCV distributions; both are pinned to the same version to limit conflicts. If `cv2` imports fail, rebuild a clean environment and review the dependencies.

For Linux, install the platform's Tkinter, PortAudio and speech synthesis packages (for example, on Debian/Ubuntu: `python3-tk`, `portaudio19-dev`, `espeak-ng`, and the Python venv/development packages matching your Python installation). Create a virtual environment with `python3.11 -m venv .venv`, then use `.venv/bin/python` instead of the Windows Python executable in the commands above. Linux/macOS are not tested release targets.

## How to use

The current interface and speech are in Brazilian Portuguese, even though this README is in English. For a controlled demonstration with consenting participants:

1. Open the application and allow webcam and microphone access.
2. Stand in front of the webcam. An unknown face is labeled `DESCONHECIDO` (unknown).
3. When the program asks `Quem é você?` (Who are you?), say `Registrar` (register).
4. Say your name when prompted. Keep only one face visible and follow the five on-screen pose instructions, roughly five seconds apart.
5. On subsequent recognition, the system displays the enrolled name in blue and may greet the participant by voice.
6. Press `Q` to exit. The `A` key only prints enrollment guidance to the terminal.

## Project structure

```text
app.py              # Original application source
requirements.txt    # Suggested Python dependencies
README.md           # English documentation
README.pt-BR.md     # Portuguese documentation
.gitignore          # Excludes runtime data and temporary files
```

Runtime-only files: `rostos.db`, `fotos_cadastradas/`. The original SQLite file was empty and is intentionally not included.

## Privacy and limitations

This is a research/academic prototype, not a production identity or security system. Use only in controlled demonstrations with informed, consenting participants. It stores sensitive facial images and embeddings without encryption or an administrative deletion interface; speech transcription uses an external Google service. Do not upload biometric records to GitHub. The project has no liveness detection, no pose verification, no access control, and no independently established accuracy or performance metrics. Do not use it for covert identification, security decisions, or public deployment. The original internship PDFs are not included in this shareable package because they contain internal context and photographs; share them separately only if authorized.

## Authors

- Victor Mateus Machado Vieira
- Jackson Garcês Damasceno

Computer Engineering — Universidade CEUMA, 2026.

## Distribution

No software license was supplied with the original project. No new license is granted by this packaging. Obtain authorization from the project authors and the internship organization before publishing or distributing the code publicly.
