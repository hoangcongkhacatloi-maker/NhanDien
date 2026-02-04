import os
import cv2
import time
import json
import numpy as np
from datetime import datetime
import pygame
from fastapi import FastAPI, Body, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import threading
from gtts import gTTS 
import requests
from insightface.app import FaceAnalysis
from ultralytics import YOLO
from gtts import gTTS
from pydub import AudioSegment
import os

# Tối ưu hóa hệ thống
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# ================== CẤU HÌNH ==================
CAMERA_SOURCE = "rtsp://admin:hd543211@192.168.1.4:1127/Streaming/Channels/101"
BASE_DIR = r"C:\VScode\NhaDien\NhanDIen\backend"
DATASET_FOLDER = os.path.join(BASE_DIR, "dataset")
CHAMCONG_DIR = os.path.join(BASE_DIR, "ChamCong")
ATTENDANCE_FILE = os.path.join(CHAMCONG_DIR, "ChamCong.json")
CAPTURE_DIR = os.path.join(BASE_DIR, "captured_faces")
AUDIO_RETRY = os.path.join(BASE_DIR, "audio", "xin-vui-lòng-thử-lại.wav")

THRESHOLD = 0.6
DETECT_DELAY = 1.5
YOLO_MODEL_PATH = r"C:\VScode\NhaDien\my_model\nhandien\weights\best.pt"
YOLO_CONF = 0.5
COOLDOWN_SECONDS = 300
YOLO_AUDIO_COOLDOWN = 3

YOLO_AUDIO_MAP = {
    "with_mask": "xin hãy tháo khẩu tr.wav",
    "glasses": "xin hãy tháo kính ra.wav",
    "hat": "xin hãy tháo nón ra.wav",
}

# ================== BIẾN TOÀN CỤC & CACHE ==================
AI_ENABLED = True
latest_frame = None
detect_start_time = None
detect_current_state = None
last_processed_time = {}
last_yolo_alert_time = {}
last_retry_audio_time = 0 # Quản lý delay báo thử lại
ai_lock = threading.Lock()
last_retry_audio_time = 0
camera_lock = threading.Lock()

last_faces_cache = []  
last_ai_time = 0
AI_INTERVAL = 0.05 

# FPT AI v5 Configuration
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# ================== KHỞI TẠO AI (GPU) ==================
yolo_model = YOLO(YOLO_MODEL_PATH)
yolo_model.to('cuda')

face_app = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
try:
    face_app.prepare(ctx_id=0, det_size=(320, 320))
    print("✅ Hệ thống chạy trên GPU (CUDA).")
except:
    face_app.prepare(ctx_id=-1, det_size=(320, 320))

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()

# ================== HÀM XỬ LÝ DATABASE & AI ==================
def build_embeddings_db():
    print("🔄 Đang kiểm tra và cập nhật Database Embedding...")
    if not os.path.exists(DATASET_FOLDER): return
    for person in os.listdir(DATASET_FOLDER):
        person_path = os.path.join(DATASET_FOLDER, person)
        if not os.path.isdir(person_path): continue
        emb_dir = os.path.join(person_path, "embedding")
        os.makedirs(emb_dir, exist_ok=True)
        for file in os.listdir(person_path):
            if not file.lower().endswith((".jpg", ".png", ".jpeg")): continue
            emb_file = os.path.join(emb_dir, file.rsplit(".", 1)[0] + ".bin")
            if os.path.exists(emb_file): continue
            img = cv2.imread(os.path.join(person_path, file))
            if img is not None:
                faces = face_app.get(img)
                if faces:
                    faces[0].normed_embedding.astype(np.float32).tofile(emb_file)
                    print(f"✔ Đã tạo Embedding: {person}/{file}")

def recognize(emb):
    best_name, best_score = "Unknown", 0
    for person in os.listdir(DATASET_FOLDER):
        emb_dir = os.path.join(DATASET_FOLDER, person, "embedding")
        if not os.path.exists(emb_dir): continue
        for ef in os.listdir(emb_dir):
            if not ef.endswith(".bin"): continue
            stored = np.fromfile(os.path.join(emb_dir, ef), dtype=np.float32)
            score = np.dot(emb, stored) / (np.linalg.norm(emb) * np.linalg.norm(stored))
            if score > THRESHOLD and score > best_score:
                best_name, best_score = person, score
    return best_name, best_score

# ================== HÀM TẠO ÂM THANH GOOGLE TTS ==================
def generate_audio_ai(text, output_path):
    """Sử dụng gTTS tạo MP3 trực tiếp (Bỏ phần chuyển đổi WAV)"""
    try:
        # Đảm bảo đuôi file luôn là .mp3
        if not output_path.endswith(".mp3"):
            output_path = output_path.rsplit(".", 1)[0] + ".mp3"
            
        tts = gTTS(text=text, lang="vi")
        tts.save(output_path)
        print(f"✅ Đã tạo file MP3: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Lỗi gTTS: {e}")
        return False

def save_attendance(frame, name_raw):
    if "-" not in name_raw: return False
    ten, ma_nv = [x.strip() for x in name_raw.split("-", 1)]
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    if ma_nv in last_processed_time and (time.time() - last_processed_time[ma_nv]) < COOLDOWN_SECONDS: return False
    
    if not os.path.exists(ATTENDANCE_FILE): data = []
    else:
        with open(ATTENDANCE_FILE, "r", encoding="utf-8") as f:
            try: data = json.load(f)
            except: data = []
    
    if any(r.get("ma_nv") == ma_nv and r.get("thoi_gian", "").startswith(today) for r in data): return False
    person_dir = os.path.join(CAPTURE_DIR, name_raw)
    os.makedirs(person_dir, exist_ok=True)
    photo_name = f"{today}_{now.strftime('%H-%M-%S')}.jpg"
    cv2.imwrite(os.path.join(person_dir, photo_name), frame)
    data.append({"ten": ten, "ma_nv": ma_nv, "photo_path": f"captured_faces/{name_raw}/{photo_name}", "thoi_gian": now.strftime("%Y-%m-%dT%H:%M:%S")})
    with open(ATTENDANCE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    last_processed_time[ma_nv] = time.time()
    return True

# ================== AI CORE (PHỐI HỢP YOLO & FACE) ==================
def process_frame(frame):
    global last_faces_cache, AI_ENABLED, last_ai_time, last_yolo_alert_time, detect_start_time, detect_current_state, last_retry_audio_time

    frame_display = cv2.resize(frame, (640, 360))
    if not AI_ENABLED: return frame_display
    
    now = time.time()
    if now - last_ai_time > AI_INTERVAL:
        last_ai_time = now
        with ai_lock:
            # 1. Chạy YOLO (Cảnh báo khẩu trang, kính, nón)
            results = yolo_model(frame_display, conf=YOLO_CONF, verbose=False)
            yolo_found = []
            for r in results:
                for box in r.boxes:
                    lbl = yolo_model.names.get(int(box.cls[0]))
                    if lbl in YOLO_AUDIO_MAP:
                        yolo_found.append({"lbl": lbl, "box": [int(x) for x in box.xyxy[0]]})

            if yolo_found:
                temp_cache = []
                for det in yolo_found:
                    if now - last_yolo_alert_time.get(det["lbl"], 0) > YOLO_AUDIO_COOLDOWN:
                        # ĐẢM BẢO: Các file trong YOLO_AUDIO_MAP cũng phải là đuôi .mp3
                        audio_path = os.path.join(BASE_DIR, "audio", YOLO_AUDIO_MAP[det["lbl"]])
                        if os.path.exists(audio_path):
                            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
                            pygame.mixer.music.load(audio_path)
                            pygame.mixer.music.play()
                        last_yolo_alert_time[det["lbl"]] = now
                    temp_cache.append({"box": det["box"], "name": det["lbl"], "color": (0, 0, 255)})
                last_faces_cache = temp_cache
                detect_start_time = detect_current_state = None
            else:
                # 2. CHẠY NHẬN DIỆN KHUÔN MẶT
                faces = face_app.get(frame_display)
                temp_cache = []
                recognized_names = []
                
                if faces:
                    for face in faces:
                        name, score = recognize(face.normed_embedding)
                        known = (name != "Unknown" and score >= THRESHOLD)
                        if known: recognized_names.append(name)
                        temp_cache.append({
                            "box": face.bbox.astype(int).tolist(),
                            "name": name if known else "Unknown",
                            "color": (0, 255, 0) if known else (0, 0, 255)
                        })

                    state = "SUCCESS" if (recognized_names and len(recognized_names) == len(faces)) else "FAIL"
                    if detect_current_state != state:
                        detect_current_state = state; detect_start_time = now

                    if detect_start_time and (now - detect_start_time >= DETECT_DELAY):
                        if state == "SUCCESS":
                            for n in recognized_names:
                                if save_attendance(frame, n):
                                    # CHỈNH SỬA TẠI ĐÂY: Phát file .mp3 theo tên folder (Tên-Mã)
                                    audio_p = os.path.join(BASE_DIR, "audio", f"{n}.mp3")
                                    
                                    if os.path.exists(audio_p):
                                        try:
                                            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
                                            pygame.mixer.music.load(audio_p)
                                            pygame.mixer.music.play()
                                            print(f"🔊 Đang phát âm thanh: {n}.mp3")
                                        except Exception as e:
                                            print(f"❌ Lỗi phát nhạc: {e}")
                        else:
                            # Cảnh báo "Thử lại" mỗi 5 giây
                            if now - last_retry_audio_time > 5:
                                # ĐẢM BẢO: AUDIO_RETRY trỏ đến file .mp3
                                if os.path.exists(AUDIO_RETRY):
                                    pygame.mixer.music.load(AUDIO_RETRY)
                                    pygame.mixer.music.play()
                                    last_retry_audio_time = now
                        detect_start_time = detect_current_state = None
                else:
                    detect_start_time = detect_current_state = None
                last_faces_cache = temp_cache

    # Vẽ khung lên màn hình
    for item in last_faces_cache:
        box = item.get("box")
        if box:
            cv2.rectangle(frame_display, (box[0], box[1]), (box[2], box[3]), item["color"], 2)
            cv2.putText(frame_display, item["name"], (box[0], box[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, item["color"], 2)

    return frame_display

# ================== CAMERA & API ROUTES ==================
def camera_loop():
    global latest_frame
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    warmup = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.release(); time.sleep(2); cap = cv2.VideoCapture(CAMERA_SOURCE); warmup = 0; continue
        if warmup < 5: warmup += 1; continue
        with camera_lock: latest_frame = frame.copy()
        time.sleep(0.01)

threading.Thread(target=camera_loop, daemon=True).start()

def gen_frames():
    while True:
        with camera_lock:
            if latest_frame is None: continue
            f = latest_frame.copy()
        proc = process_frame(f)
        _, buf = cv2.imencode(".jpg", proc)
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/video")
def video(): return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/capture")
def capture_image(payload: dict = Body(...)):
    global latest_frame
    if latest_frame is None:
        raise HTTPException(status_code=400, detail="Không có frame từ camera")

    name = payload.get("name", "").strip()
    code = payload.get("code", "").strip()
    
    # 1. Định nghĩa Tên-Mã nhân viên (Dùng làm tên folder và tên file audio)
    target = f"{name}-{code}" 
    
    # 2. Tạo folder ảnh: dataset/Tên-Mã
    path = os.path.join(DATASET_FOLDER, target)
    os.makedirs(path, exist_ok=True)
    
    # Lưu ảnh vào folder vừa tạo
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(os.path.join(path, filename), latest_frame)

    # 3. Tạo file âm thanh: audio/Tên-Mã.mp3
    # Đảm bảo AUDIO_DIR đã được định nghĩa ở đầu file: AUDIO_DIR = os.path.join(BASE_DIR, "audio")
    audio_path = os.path.join(AUDIO_DIR, f"{target}.mp3")
    
    if not os.path.exists(audio_path):
        # Truyền đúng target vào để gTTS tạo file
        threading.Thread(
            target=generate_audio_ai, 
            args=(f"Xin chào {name}", audio_path), 
            daemon=True
        ).start()

    build_embeddings_db()
    return {"success": True, "message": f"Đã lưu nhân viên {target} và đang tạo audio"}

@app.get("/employees")
def api_get_employees():
    out = []
    if os.path.exists(DATASET_FOLDER):
        for f in sorted(os.listdir(DATASET_FOLDER)):
            if "-" in f:
                p = f.split("-", 1)
                out.append({"name": p[0].strip(), "code": p[1].strip(), "folder": f})
    return out

@app.get("/folders")
def list_folders():
    return sorted([f for f in os.listdir(DATASET_FOLDER) if os.path.isdir(os.path.join(DATASET_FOLDER, f))])

@app.delete("/folders/{folder_name}")
def delete_folder(folder_name: str):
    path = os.path.join(DATASET_FOLDER, folder_name)
    if os.path.exists(path): shutil.rmtree(path); return {"success": True}
    raise HTTPException(status_code=404)

@app.get("/capture/preview")
def capture_preview():
    global latest_frame
    if latest_frame is None:
        raise HTTPException(status_code=400, detail="Camera không khả dụng")
    
    with camera_lock:
        # Lấy khung hình hiện tại
        frame = latest_frame.copy()
    
    # Mã hóa frame thành định dạng ảnh JPEG để gửi qua Web
    _, buffer = cv2.imencode('.jpg', frame)
    
    # Trả về dữ liệu ảnh trực tiếp
    return Response(content=buffer.tobytes(), media_type="image/jpeg")

@app.get("/photo")
def api_serve_photo(path: str = ""):
    full = os.path.realpath(os.path.join(BASE_DIR, path.replace("/", os.sep)))
    if not full.startswith(os.path.realpath(CAPTURE_DIR)) or not os.path.isfile(full): raise HTTPException(status_code=404)
    with open(full, "rb") as f: return Response(content=f.read(), media_type="image/jpeg")

@app.get("/timekeeping/history")
def api_get_attendance_history():
    if not os.path.exists(ATTENDANCE_FILE): return []
    with open(ATTENDANCE_FILE, "r", encoding="utf-8") as f: return json.load(f)

if __name__ == "__main__":
    build_embeddings_db()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)