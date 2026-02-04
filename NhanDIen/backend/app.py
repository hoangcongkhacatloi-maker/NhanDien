import os
import cv2
import time
import json
import numpy as np
from datetime import datetime
import pygame
import base64
import uvicorn
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
from collections import deque

attendance_queue = deque()
attendance_lock = threading.Lock()
attendance_processing = False
import os

# Tối ưu hóa hệ thống
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# ================== CẤU HÌNH ==================
CAMERA_SOURCE = "rtsp://admin:hd543211@192.168.1.4:1127/Streaming/Channels/101"
BASE_DIR = r"C:\VScode\NhanDien\NhanDIen\backend"
DATASET_FOLDER = os.path.join(BASE_DIR, "dataset")
CHAMCONG_DIR = os.path.join(BASE_DIR, "ChamCong")
ATTENDANCE_FILE = os.path.join(CHAMCONG_DIR, "ChamCong.json")
CAPTURE_DIR = os.path.join(BASE_DIR, "captured_faces")
AUDIO_RETRY = os.path.join(BASE_DIR, "audio", "xin-vui-long-thu-lai.mp3")

THRESHOLD = 0.6
DETECT_DELAY = 1.5
YOLO_MODEL_PATH = r"C:\VScode\NhanDien\my_model\nhandien\weights\best.pt"
YOLO_CONF = 0.5
COOLDOWN_SECONDS = 300
YOLO_AUDIO_COOLDOWN = 3

YOLO_AUDIO_MAP = {
    "with_mask": "thao_khau_trang.mp3",
    "glasses": "thao_kinh.mp3",
    "hat": "thao_non.mp3",
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

def process_attendance_queue():
    global attendance_processing
    while True:
        with attendance_lock:
            if not attendance_queue:
                attendance_processing = False
                return
            name_to_process, frame_to_process = attendance_queue.popleft()

        # BƯỚC 1: GHI NHẬN VÀO FILE TRƯỚC
        success_name = save_attendance(frame_to_process, name_to_process)

        # BƯỚC 2: PHÁT AUDIO SAU KHI LƯU XONG
        if success_name:
            audio_p = os.path.join(AUDIO_DIR, f"{success_name}.mp3")
            
            if os.path.exists(audio_p):
                try:
                    # Nếu đang phát dở (YOLO alert chẳng hạn) thì dừng để ưu tiên chào nhân viên
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                        
                    pygame.mixer.music.load(audio_p)
                    pygame.mixer.music.play()
                    
                    print(f"🔊 Đang chào: {success_name}")
                    
                    # Chờ phát xong âm thanh mới xử lý người tiếp theo (để không bị đè tiếng)
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                except Exception as e:
                    print(f"❌ Lỗi mixer: {e}")
            else:
                print(f"⚠️ Thiếu file audio: {audio_p}")

        time.sleep(0.2) # Nghỉ ngắn

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
    if "-" not in name_raw: return None
    ten, ma_nv = [x.strip() for x in name_raw.split("-", 1)]
    now = datetime.now()
    
    # BƯỚC 1: KIỂM TRA COOLDOWN (Ví dụ 300s = 5 phút mới lưu lại 1 lần)
    # Nếu muốn lưu liên tục để test, hãy chỉnh COOLDOWN_SECONDS = 10 ở đầu file
    if ma_nv in last_processed_time:
        if (time.time() - last_processed_time[ma_nv]) < COOLDOWN_SECONDS:
            return None # Vẫn trong thời gian chờ, không lưu thêm

    # BƯỚC 2: ĐỌC DỮ LIỆU CŨ
    try:
        if not os.path.exists(ATTENDANCE_FILE):
            data = []
        else:
            with open(ATTENDANCE_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                data = json.loads(content) if content else []
    except:
        data = []

    # BƯỚC 3: LƯU ẢNH (Mỗi tấm ảnh sẽ có tên theo giờ phút giây để không bị ghi đè)
    person_dir = os.path.join(CAPTURE_DIR, name_raw)
    os.makedirs(person_dir, exist_ok=True)
    
    # Tên file ảnh bao gồm Ngày_GiờPhútGiây để mỗi lần lưu là 1 file khác nhau
    timestamp_str = now.strftime('%Y-%m-%d_%H-%M-%S')
    photo_name = f"{timestamp_str}.jpg"
    photo_full_path = os.path.join(person_dir, photo_name)
    
    cv2.imwrite(photo_full_path, frame)

    # BƯỚC 4: GHI VÀO JSON LỊCH SỬ
    new_record = {
        "ten": ten,
        "ma_nv": ma_nv,
        "photo_path": f"captured_faces/{name_raw}/{photo_name}",
        "thoi_gian": now.strftime("%Y-%m-%dT%H:%M:%S")
    }
    data.append(new_record)
    
    with open(ATTENDANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Cập nhật lại thời gian xử lý cuối cùng của nhân viên này
    last_processed_time[ma_nv] = time.time()
    
    print(f"📸 Đã lưu ảnh mới & Ghi danh: {ten} lúc {timestamp_str}")
    return name_raw

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
                            with attendance_lock:
                                for n in recognized_names:
                                    # tránh trùng người đã có trong queue
                                    if n not in [x[0] for x in attendance_queue]:
                                        attendance_queue.append((n, frame.copy()))

                                # nếu chưa có thread xử lý → bật
                                global attendance_processing
                                if not attendance_processing:
                                    attendance_processing = True
                                    threading.Thread(
                                        target=process_attendance_queue,
                                        daemon=True
                                    ).start()

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
    selected_folder = payload.get("folder", "").strip()
    name = payload.get("name", "").strip()
    code = payload.get("code", "").strip()
    images_base64 = payload.get("images", []) # Nhận danh sách ảnh Base64

    target = selected_folder if selected_folder else f"{name}-{code}"
    path = os.path.join(DATASET_FOLDER, target)
    os.makedirs(path, exist_ok=True)

    saved_count = 0
    for img_data in images_base64:
        try:
            # Tách bỏ phần đầu "data:image/jpeg;base64,"
            header, encoded = img_data.split(",", 1)
            data = base64.b64decode(encoded)
            
            # Tạo tên file duy nhất
            filename = f"cap_{datetime.now().strftime('%H%M%S_%f')}.jpg"
            with open(os.path.join(path, filename), "wb") as f:
                f.write(data)
            saved_count += 1
        except Exception as e:
            print(f"❌ Lỗi lưu ảnh Base64: {e}")

    # Tạo âm thanh nếu chưa có
    audio_path = os.path.join(AUDIO_DIR, f"{target}.mp3")
    if not os.path.exists(audio_path):
        display_name = target.split("-")[0] if "-" in target else target
        generate_audio_ai(f"Xin chào {display_name}", audio_path)

    build_embeddings_db()
    return {"success": True, "message": f"Đã lưu {saved_count} ảnh vào {target}"}

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

# Route để tắt AI khi bắt đầu vào trang Chụp ảnh
@app.post("/ai/disable")
def disable_ai():
    global AI_ENABLED
    AI_ENABLED = False
    print("🤖 AI Recognition: DISABLED")
    return {"success": True}

# Route để bật lại AI khi thoát khỏi trang Chụp ảnh
@app.post("/ai/enable")
def enable_ai():
    global AI_ENABLED
    AI_ENABLED = True
    print("🤖 AI Recognition: ENABLED")
    return {"success": True}

@app.get("/photo")
def api_serve_photo(path: str = ""):
    full = os.path.realpath(os.path.join(BASE_DIR, path.replace("/", os.sep)))
    if not full.startswith(os.path.realpath(CAPTURE_DIR)) or not os.path.isfile(full): raise HTTPException(status_code=404)
    with open(full, "rb") as f: return Response(content=f.read(), media_type="image/jpeg")

@app.get("/timekeeping/history")
def api_get_attendance_history():
    if not os.path.exists(ATTENDANCE_FILE): return []
    with open(ATTENDANCE_FILE, "r", encoding="utf-8") as f: return json.load(f)

# Thêm vào trong khối if __name__ == "__main__":
if __name__ == "__main__":
    # Đảm bảo thư mục tồn tại
    os.makedirs(CHAMCONG_DIR, exist_ok=True)
    # Khởi tạo file JSON nếu chưa có hoặc bị trống
    if not os.path.exists(ATTENDANCE_FILE) or os.stat(ATTENDANCE_FILE).st_size == 0:
        with open(ATTENDANCE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
            
    build_embeddings_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)