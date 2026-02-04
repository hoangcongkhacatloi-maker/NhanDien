import { useEffect, useState } from "react";
import "../css/Capture.css";

const BACKEND_URL = "http://localhost:8000";

function Capture() {
  const [folders, setFolders] = useState([]);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState("");
  const [previewImages, setPreviewImages] = useState([]);

  // ================= AI: TẮT / BẬT =================
  useEffect(() => {
    fetch(`${BACKEND_URL}/ai/disable`, { method: "POST" }).catch(() => {});
    return () => {
      fetch(`${BACKEND_URL}/ai/enable`, { method: "POST" }).catch(() => {});
    };
  }, []);

  // ================= LOAD FOLDERS =================
  const loadFolders = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/folders`);
      setFolders(await res.json());
    } catch {
      console.error("Load folder lỗi");
    }
  };

  useEffect(() => {
    loadFolders();
  }, []);

  const handleDeleteFolder = async () => {
    if (!selectedFolder) return;

    const ok = window.confirm(
      `⚠️ Bạn có chắc muốn xoá nhân viên "${selectedFolder}"?\nToàn bộ ảnh sẽ bị xoá!`,
    );
    if (!ok) return;

    try {
      const res = await fetch(`${BACKEND_URL}/folders/${selectedFolder}`, {
        method: "DELETE",
      });
      const data = await res.json();

      if (data.success) {
        setStatus("🗑️ Đã xoá nhân viên");
        setSelectedFolder("");
        setPreviewImages([]);
        loadFolders();
      } else {
        setStatus("❌ Xoá thất bại");
      }
    } catch {
      setStatus("❌ Lỗi backend khi xoá");
    }
  };

  // ================= CHỤP ẢNH (LIÊN TỤC) =================
  const handlePreview = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/capture/preview`);
      const blob = await res.blob();
      
      // Chuyển Blob thành Base64
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = () => {
        const base64data = reader.result;
        setPreviewImages((prev) => [base64data, ...prev]); // Lưu Base64 vào state
      };
    } catch {
      setStatus("❌ Không chụp được ảnh");
    }
  };

  // ================= XOÁ 1 ẢNH =================
  const handleRemovePreview = (index) => {
    setPreviewImages((prev) => prev.filter((_, i) => i !== index));
  };

  // ================= LƯU ẢNH =================
  // Sửa lại hàm này trong Capture.js
  const handleCapture = async () => {
    if (previewImages.length === 0) {
      setStatus("⚠️ Chưa có ảnh");
      return;
    }
    if (!selectedFolder && (!name || !code)) {
      setStatus("⚠️ Thiếu Tên hoặc Mã NV");
      return;
    }

    setStatus("📤 Đang lưu...");
    try {
      const res = await fetch(`${BACKEND_URL}/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          folder: selectedFolder,
          name,
          code,
          images: previewImages, // Gửi toàn bộ mảng Base64 sang Python
        }),
      });

      const data = await res.json();
      if (data.success) {
        setStatus(`✅ Đã lưu khớp ${previewImages.length} ảnh`);
        setPreviewImages([]);
        if (!selectedFolder) loadFolders();
      }
    } catch {
      setStatus("❌ Lỗi kết nối server");
    }
  };

  return (
    <div className="capture fade-in">
      <h1>📸 Chụp ảnh nhân viên</h1>
      <div className="status-badge inactive">AI đã tắt khi chụp ảnh</div>

      {/* CAMERA + PREVIEW */}
      <div className="capture-layout">
        {/* CAMERA */}
        <div className="camera-column">
          <div className="video-wrapper">
            <img
              src={`${BACKEND_URL}/video`}
              className="video-stream"
              alt="Camera"
            />
          </div>

          <button className="btn-preview" onClick={handlePreview}>
            📸 Chụp ảnh
          </button>

          <button
            className="btn-save"
            onClick={handleCapture}
            disabled={previewImages.length === 0}
          >
            💾 Lưu ảnh ({previewImages.length})
          </button>
        </div>

        {/* PREVIEW */}
        <div className="preview-column">
          {previewImages.length === 0 && (
            <div className="preview-empty">Chưa có ảnh</div>
          )}

          {previewImages.map((img, index) => (
            <div className="preview-item" key={index}>
              <img src={img} alt={`preview-${index}`} />
              <button
                className="btn-delete small"
                onClick={() => handleRemovePreview(index)}
              >
                ❌
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* FORM */}
      <div className="capture-form">
        <div className="employee-row">
          <div className="employee-select">
            <label>Nhân viên</label>
            <select
              value={selectedFolder}
              onChange={(e) => {
                setSelectedFolder(e.target.value);
                setName("");
                setCode("");
              }}
            >
              <option value="">＋ Tạo mới</option>
              {folders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
        </div>

        {!selectedFolder && (
          <div className="input-row">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Tên nhân viên"
            />
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Mã NV"
            />
          </div>
        )}

        {selectedFolder && (
          <button className="btn-delete-folder" onClick={handleDeleteFolder}>
            🗑️ Xoá nhân viên
          </button>
        )}
      </div>
    </div>
  );
}

export default Capture;
