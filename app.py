"""Reconhecimento facial com malha oculta, voz e cadastro autorizado."""
import json
import re
import queue
import subprocess
import sys
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from tkinter import Tk, Label, BOTH

import cv2
import mediapipe as mp
import numpy as np
import pyttsx3
import speech_recognition as sr
from deepface import DeepFace
from PIL import Image, ImageTk

DB = Path(__file__).resolve().parent / "rostos.db"
PHOTOS_DIR = Path(__file__).resolve().parent / "fotos_cadastradas"
MODEL = "Facenet512"
THRESHOLD = 0.30
UNKNOWN = "DESCONHECIDO"
CAPTURE_INTERVAL = 5.0  # Segundos entre capturas
GREETING_COOLDOWN = 10 * 60  # 10 minutos por pessoa
PHOTO_INSTRUCTIONS = (
    "Centralize o rosto",
    "Vire o rosto para a direita",
    "Vire o rosto para a esquerda",
    "Vire o rosto para baixo",
    "Vire o rosto para cima",
)


def connect_db():
    db = sqlite3.connect(DB)
    db.execute("""CREATE TABLE IF NOT EXISTS faces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, photo BLOB NOT NULL,
        model_name TEXT NOT NULL, embedding TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    db.commit()
    return db


def load_faces(db):
    return [(name, np.asarray(json.loads(vec), dtype=np.float32))
            for name, vec in db.execute(
                "SELECT name, embedding FROM faces WHERE model_name=?", (MODEL,))]


def embed(face):
    result = DeepFace.represent(img_path=face, model_name=MODEL,
                                detector_backend="skip", enforce_detection=False)
    if not result:
        raise ValueError("Não foi possível gerar o embedding.")
    return np.asarray(result[0]["embedding"], dtype=np.float32)


def recognize(face, records):
    vector = embed(face)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    best_name, best_distance = None, float("inf")
    for name, saved in records:
        if saved.shape != vector.shape:
            continue
        denominator = norm * np.linalg.norm(saved)
        if denominator == 0:
            continue
        distance = 1 - float(np.dot(vector, saved) / denominator)
        if distance < best_distance:
            best_name, best_distance = name, distance
    return best_name if best_distance <= THRESHOLD else None


class SpeechManager:
    """Fila serializada; cada fala usa um processo TTS independente no Windows.

    Evita a falha do SAPI/pyttsx3 em que a primeira mensagem toca e as
    seguintes aparecem apenas no terminal.
    """
    def __init__(self, stop):
        self.stop = stop
        self.messages = queue.Queue()
        self.voice_session = threading.Event()
        self.last_greeting = {}
        self.pending = set()
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()

    @staticmethod
    def _play(message):
        if sys.platform == "win32":
            # Um processo por fala elimina o estado travado do SAPI/pyttsx3.
            # Texto enviado via stdin, sem problemas de aspas ou nomes especiais.
            script = r"""
Add-Type -AssemblyName System.Speech
$tts = New-Object System.Speech.Synthesis.SpeechSynthesizer
$tts.Rate = -1
$voice = $tts.GetInstalledVoices() | Where-Object {
    $_.VoiceInfo.Culture.Name -eq 'pt-BR'
} | Select-Object -First 1
if ($voice) { $tts.SelectVoice($voice.VoiceInfo.Name) }
try {
    $message = [Console]::In.ReadToEnd()
    $tts.Speak($message)
} finally { $tts.Dispose() }
"""
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                input=message, text=True, encoding="utf-8",
                capture_output=True, timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Falha no sintetizador Windows")
        else:
            engine = pyttsx3.init()
            try:
                engine.setProperty("rate", 150)
                engine.say(message)
                engine.runAndWait()
            finally:
                engine.stop()

    def _worker(self):
        while not self.stop.is_set():
            try:
                kind, name, message, finished = self.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                # Aguardar o fim da interação de cadastro, sem perder a saudação.
                if kind == "greeting":
                    while self.voice_session.is_set() and not self.stop.is_set():
                        time.sleep(0.1)
                if self.stop.is_set():
                    break
                print("Sistema (falando):", message)
                self._play(message)
                print("Sistema (áudio concluído):", message)
                if kind == "greeting":
                    with self.lock:
                        self.last_greeting[name] = time.monotonic()
            except Exception as exc:
                print("ERRO NA VOZ (saudação não contabilizada):", repr(exc))
            finally:
                if kind == "greeting":
                    with self.lock:
                        self.pending.discard(name)
                if finished is not None:
                    finished.set()
                self.messages.task_done()

    def say(self, message):
        finished = threading.Event()
        self.messages.put(("dialog", None, message, finished))
        if not finished.wait(timeout=50):
            print("AVISO: tempo limite esperando fala de cadastro.")

    def greet(self, name):
        key = normalized_words(name).strip()
        if not key or key == normalized_words(UNKNOWN):
            return
        with self.lock:
            if key in self.pending:
                return
            if time.monotonic() - self.last_greeting.get(key, float("-inf")) < GREETING_COOLDOWN:
                return
            self.pending.add(key)
        print("Saudação colocada na fila:", name)
        self.messages.put(("greeting", key,
                           f"Olá, {name.title()}, tenha um bom dia!", None))


def normalized_words(text):
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def enrollment_embeddings(name, samples, results):
    """Calcula embeddings em segundo plano; a câmera continua atualizando."""
    try:
        vectors = [embed(crop) for crop in samples]
        vectors = [v / np.linalg.norm(v) for v in vectors if np.linalg.norm(v) > 0]
        if len(vectors) != 5:
            raise ValueError("Nem todas as 5 imagens produziram embeddings válidos.")
        # Média de cinco vetores unitários, normalizada para comparação por cosseno.
        average = np.mean(vectors, axis=0)
        average /= np.linalg.norm(average)
        # Uma amostra JPEG é armazenada como referência, junto com o embedding médio.
        ok, encoded = cv2.imencode(".jpg", samples[0])
        if not ok:
            raise ValueError("Falha ao codificar imagem de referência.")
        results.put((name, encoded.tobytes(), average.tolist(), None))
    except Exception as exc:
        results.put((name, None, None, str(exc)))



def save_enrollment_photos(name, samples):
    """Salva as 5 capturas JPEG sem sobrescrever cadastros anteriores."""
    safe_name = re.sub(r"[^\w-]+", "_", normalized_words(name), flags=re.UNICODE).strip("_.")
    safe_name = safe_name[:60] or "pessoa"
    # Uma pasta por pessoa; um novo cadastro substitui foto_01 a foto_05.
    folder = PHOTOS_DIR / safe_name
    folder.mkdir(parents=True, exist_ok=True)
    try:
        for i, crop in enumerate(samples, start=1):
            ok, encoded = cv2.imencode(".jpg", crop)
            if not ok:
                raise ValueError(f"Não foi possível codificar a foto {i}.")
            (folder / f"foto_{i:02d}.jpg").write_bytes(encoded.tobytes())
    except Exception:
        raise
    return folder


def voice_interaction(results, speaker):
    """Pergunta, escuta 'registrar' em qualquer frase e pede o nome por voz."""
    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as microphone:
            recognizer.adjust_for_ambient_noise(microphone, duration=0.2)
            speaker.say("Quem é você?")
            print("Diga 'Registrar' em até 8 segundos. (Microfone ativo)")
            audio = recognizer.listen(microphone, timeout=8, phrase_time_limit=10)
            spoken = recognizer.recognize_google(audio, language="pt-BR")
            print("Você disse:", spoken)
            if "registrar" not in normalized_words(spoken).split():
                results.put(("retry", None))
                return
            speaker.say("Qual é o seu nome?")
            print("Diga seu nome em até 8 segundos.")
            audio = recognizer.listen(microphone, timeout=8, phrase_time_limit=5)
            name = recognizer.recognize_google(audio, language="pt-BR").strip()
            name = " ".join(name.split())[:80]
            if not name or not any(ch.isalpha() for ch in name):
                raise ValueError("Nome inválido.")
            print("Nome reconhecido:", name)
            speaker.say(f"{name}. Olhe para a câmera para cadastrar seu rosto.")
            results.put(("enroll", name))
    except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestError,
            OSError, RuntimeError, ValueError) as exc:
        print("Não foi possível concluir a interação:", exc)
        results.put(("retry", None))
    except Exception as exc:
        print("Falha na interação por voz:", exc)
        results.put(("retry", None))
    finally:
        speaker.voice_session.clear()


def main():
    db = connect_db()
    records = load_faces(db)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        print("Não foi possível abrir a webcam.")
        db.close()
        return

    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False, max_num_faces=3, refine_landmarks=False,
        min_detection_confidence=0.5, min_tracking_confidence=0.5)
    root = Tk()
    root.title("Reconhecimento Facial — SYOS SPACE")
    root.geometry("1000x700")
    screen = Label(root)
    screen.pack(fill=BOTH, expand=True)

    jobs, recognized, voice_results = queue.Queue(maxsize=1), queue.Queue(), queue.Queue()
    enrollment_results = queue.Queue()
    stop = threading.Event()
    speaker = SpeechManager(stop)
    faces, frame_count, unknown_since = [], 0, None
    asked, voice_busy, registering, running = False, False, False, True
    next_id = 0
    enrollment = None  # Nome, amostras, última captura e rosto-alvo
    enrollment_busy = False
    latest_frame = None
    retry_at = 0.0  # Próxima tentativa de pergunta por voz
    RETRY_DELAY = 7  # Segundos após terminar a tentativa anterior

    def recognition_worker():
        while not stop.is_set():
            try:
                face_id, crop = jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                match = recognize(crop, records)
            except Exception as exc:
                print("Falha ao reconhecer rosto:", exc)
                match = None
            recognized.put((face_id, match))

    threading.Thread(target=recognition_worker, daemon=True).start()

    def register(name):
        """Inicia coleta automática, sem abrir seletor de arquivos."""
        nonlocal registering, enrollment, unknown_since, asked
        if registering or not running or not name:
            return
        registering = True
        unknown_since, asked = None, True
        enrollment = {"name": name, "samples": [],
                      "next_capture": time.monotonic() + CAPTURE_INTERVAL,
                      "started": time.monotonic()}
        print(f"Cadastro de {name}: mantenha um único rosto diante da câmera.")
        print(f"Foto 1/5: {PHOTO_INSTRUCTIONS[0]} (em 5 segundos).")

    def close():
        nonlocal running
        if not running:
            return
        running = False
        stop.set()
        cap.release()
        mesh.close()
        root.destroy()

    def update():
        nonlocal faces, frame_count, unknown_since, asked, voice_busy, next_id, retry_at, enrollment, enrollment_busy, registering, records
        if not running:
            return
        ok, frame = cap.read()
        if not ok:
            close()
            return
        h, w = frame.shape[:2]

        # A malha é calculada, mas nunca desenhada na webcam.
        if frame_count % 3 == 0:
            small = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            result = mesh.process(rgb)
            previous, updated = faces, []
            for landmarks in result.multi_face_landmarks or []:
                xs = [point.x for point in landmarks.landmark]
                ys = [point.y for point in landmarks.landmark]
                x1, y1 = max(0, int(min(xs)*w)-25), max(0, int(min(ys)*h)-40)
                x2, y2 = min(w, int(max(xs)*w)+25), min(h, int(max(ys)*h)+25)
                if x2 <= x1 or y2 <= y1:
                    continue
                center = ((x1+x2)//2, (y1+y2)//2)
                nearest = min(previous, key=lambda f:
                              (f["center"][0]-center[0])**2 +
                              (f["center"][1]-center[1])**2, default=None)
                if nearest and sum((a-b)**2 for a, b in zip(
                        nearest["center"], center)) < (w*.12)**2:
                    face_id, name = nearest["id"], nearest["name"]
                else:
                    next_id += 1
                    face_id, name = next_id, UNKNOWN
                updated.append({"id": face_id, "center": center,
                                "box": (x1, y1, x2-x1, y2-y1), "name": name})
            faces = updated

        while not recognized.empty():
            face_id, name = recognized.get_nowait()
            for item in faces:
                if item["id"] == face_id:
                    item["name"] = name.upper() if name else UNKNOWN
                    if name and not registering:
                        speaker.greet(name)
                    break

        if frame_count % 10 == 0 and faces and jobs.empty() and not registering:
            item = faces[(frame_count // 10) % len(faces)]
            x, y, width, height = item["box"]
            crop = frame[y:y+height, x:x+width].copy()
            if crop.size:
                try:
                    jobs.put_nowait((item["id"], crop))
                except queue.Full:
                    pass

        while not voice_results.empty():
            action, name = voice_results.get_nowait()
            voice_busy = False
            if action == "enroll" and any(f["name"] == UNKNOWN for f in faces):
                register(name)
            else:
                if action == "enroll":
                    print("Cadastro cancelado: rosto desconhecido saiu da câmera.")
                asked = False
                retry_at = time.monotonic() + RETRY_DELAY

        if enrollment is not None and not enrollment_busy:
            # Cada etapa exibe uma orientação por 5 segundos antes da foto.
            # Para poses laterais, não exigimos que o centro do rosto permaneça fixo.
            now_capture = time.monotonic()
            if now_capture - enrollment["started"] > 90:
                print("Cadastro cancelado: tempo limite de 90 segundos.")
                enrollment, registering = None, False
                retry_at = now_capture + RETRY_DELAY
            elif now_capture >= enrollment["next_capture"]:
                if len(faces) != 1:
                    print("Aguardando exatamente um rosto para fotografar...")
                    enrollment["next_capture"] = now_capture + 1.0
                else:
                    item = faces[0]
                    x, y, fw, fh = item["box"]
                    crop = frame[y:y+fh, x:x+fw].copy()
                    if crop.size and min(crop.shape[:2]) >= 70:
                        enrollment["samples"].append(crop)
                        count = len(enrollment["samples"])
                        print(f"Foto {count}/5 capturada: {PHOTO_INSTRUCTIONS[count-1]}")
                        if count < 5:
                            enrollment["next_capture"] = now_capture + CAPTURE_INTERVAL
                            print(f"Próxima foto: {PHOTO_INSTRUCTIONS[count]} (em 5 segundos).")
                        else:
                            enrollment_busy = True
                            threading.Thread(target=enrollment_embeddings,
                                             args=(enrollment["name"],
                                                   enrollment["samples"].copy(),
                                                   enrollment_results), daemon=True).start()
                            print("Calculando média dos cinco embeddings...")
                    else:
                        print("Rosto muito pequeno; aproxime-se da câmera.")
                        enrollment["next_capture"] = now_capture + 1.0

        while not enrollment_results.empty():
            name, photo, vector, error = enrollment_results.get_nowait()
            enrollment_busy = False
            if not error:
                try:
                    with db:
                        db.execute("""INSERT INTO faces (name, photo, model_name, embedding)
                                      VALUES (?, ?, ?, ?)""",
                                   (name, sqlite3.Binary(photo), MODEL,
                                    json.dumps(vector)))
                    records = load_faces(db)
                    print(f"Cadastro concluído: {name} (5 imagens, média salva).")
                    try:
                        folder = save_enrollment_photos(name, enrollment["samples"])
                        print(f"5 fotos salvas em: {folder}")
                    except Exception as photo_error:
                        print("ATENÇÃO: cadastro salvo no SQLite, mas não foi possível "
                              f"salvar as 5 fotos em disco: {photo_error}")
                    for item in faces:
                        item["name"] = UNKNOWN
                except Exception as exc:
                    error = str(exc)
            if error:
                print("Cadastro não concluído:", error)
            enrollment, registering = None, False
            unknown_since, asked = None, False
            retry_at = time.monotonic() + RETRY_DELAY

        has_unknown = any(f["name"] == UNKNOWN for f in faces)
        now = time.monotonic()
        if has_unknown and not registering:
            if unknown_since is None:
                unknown_since = now
            elif (now - unknown_since >= 3 and not asked
                  and not voice_busy and now >= retry_at):
                asked, voice_busy = True, True
                speaker.voice_session.set()
                threading.Thread(target=voice_interaction,
                                 args=(voice_results, speaker), daemon=True).start()
        else:
            # Ao desaparecer o desconhecido, reinicia o ciclo de detecção.
            # Uma interação de voz já iniciada termina naturalmente, sem sobreposição.
            unknown_since, asked = None, False

        if enrollment is not None:
            count = len(enrollment["samples"])
            if enrollment_busy:
                instruction = "Processando as 5 fotos..."
                status = "Aguarde o cadastro"
            else:
                instruction = PHOTO_INSTRUCTIONS[count]
                remaining = max(0, int(np.ceil(enrollment["next_capture"] - time.monotonic())))
                status = f"Foto {count+1}/5 em {remaining}s"
            # Barra legível no vídeo; cv2.putText não suporta acentos em todas as fontes.
            cv2.rectangle(frame, (0, 0), (w, 105), (20, 20, 20), -1)
            cv2.putText(frame, status, (20, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            # Texto sem acentos para garantir exibição no OpenCV.
            readable = unicodedata.normalize("NFKD", instruction)
            readable = "".join(c for c in readable if not unicodedata.combining(c))
            cv2.putText(frame, readable, (20, 82),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)

        for item in faces:
            x, y, width, height = item["box"]
            name = item["name"]
            color = (0, 255, 0) if name == UNKNOWN else (255, 0, 0)
            cv2.rectangle(frame, (x, y), (x+width, y+height), color, 3)
            cv2.rectangle(frame, (x, max(0, y-40)), (x+width, y), color, -1)
            cv2.putText(frame, name, (x+10, max(18, y-12)),
                        cv2.FONT_HERSHEY_DUPLEX, .8, (255, 255, 255), 2)

        width, height = screen.winfo_width(), screen.winfo_height()
        if width > 10 and height > 10:
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
        image = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        screen.configure(image=image)
        screen.image = image
        frame_count += 1
        root.after(10, update)

    root.bind("<KeyPress-a>", lambda event: print("Cadastro automático: aguarde a pergunta e diga Registrar."))
    root.bind("<KeyPress-q>", lambda event: close())
    root.protocol("WM_DELETE_WINDOW", close)
    print("Cadastro por voz: diga Registrar, depois seu nome | Tecla Q: sair.")
    try:
        root.after(0, update)
        root.mainloop()
    finally:
        stop.set()
        if running:
            close()
        db.close()


if __name__ == "__main__":
    main()
