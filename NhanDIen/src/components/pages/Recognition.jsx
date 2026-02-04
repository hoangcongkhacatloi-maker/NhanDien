import { useState, useEffect } from "react";
import "../css/Recognition.css";

export default function Recognition() {
  const [aiEnabled, setAiEnabled] = useState(false);
  const [history, setHistory] = useState([]);
  const [gate, setGate] = useState("entrance");

  useEffect(() => {
    // VÀO TRANG → BẬT AI
    fetch("/api/ai/enable", { method: "POST" }).catch(() => {});
    setAiEnabled(true);

    loadLiveHistory();

    const interval = setInterval(loadLiveHistory, 3000);

    return () => {
      clearInterval(interval);
      fetch("/api/ai/disable", { method: "POST" }).catch(() => {});
    };
  }, []);

  const loadLiveHistory = async () => {
    try {
      const res = await fetch("/api/timekeeping/history");
      const data = await res.json();
      setHistory(Array.isArray(data) ? [...data].reverse() : []);
    } catch (err) {
      console.error("Lỗi tải lịch sử:", err);
    }
  };

  const getPhotoUrl = (path) =>
    path ? `/api/photo?path=${encodeURIComponent(path)}` : null;

  return (
    <div className="recognition">
      <h1>👁 Giám sát nhận diện AI</h1>

      <div className={`ai-status ${aiEnabled ? "on" : "off"}`}>
        Trạng thái AI: {aiEnabled ? "Đang hoạt động" : "Đang khởi động..."}
      </div>

      <div className="recognition-layout">
        {/* PHẦN BÊN TRÁI: LIVE CAMERA */}
        <div className="left-panel">
          <div className="camera-panel">
            <div className="config-subtitle">📷 Luồng Camera trực tiếp</div>
            <img src="/api/video" className="camera" alt="Live Camera" />
          </div>

          <div className="config-info" style={{ marginTop: "16px" }}>
            <p>
              <strong>Hướng dẫn:</strong> Hệ thống tự động nhận diện khuôn mặt
              nhân viên trong khung hình và lưu lại nhật ký ghi nhận ở cột bên
              phải.
            </p>
          </div>
        </div>

        {/* PHẦN BÊN PHẢI: NHẬT KÝ PHÁT HIỆN NHÂN VIÊN */}
        <div className="right-panel">
          <div
            className="exception-panel"
            style={{ height: "100%", display: "flex", flexDirection: "column" }}
          >
            <h3 className="config-subtitle">🕒 Nhật ký phát hiện (Mới nhất)</h3>

            <div
              className="override-list"
              style={{ flex: 1, maxHeight: "calc(100vh - 200px)" }}
            >
              {history.length === 0 ? (
                <div className="empty-row">Chưa có dữ liệu phát hiện...</div>
              ) : (
                history.map((row, i) => (
                  <div
                    key={i}
                    className="override-item"
                    style={{
                      gridTemplateColumns: "50px 1fr auto",
                      borderLeft: "4px solid #2563eb",
                    }}
                  >
                    {/* Ảnh khuôn mặt lúc AI phát hiện */}
                    <div className="mini-photo">
                      {row.photo_path ? (
                        <img
                          src={getPhotoUrl(row.photo_path)}
                          alt=""
                          style={{
                            width: "42px",
                            height: "42px",
                            borderRadius: "6px",
                            objectFit: "cover",
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: "42px",
                            height: "42px",
                            background: "#f3f4f6",
                            borderRadius: "6px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          👤
                        </div>
                      )}
                    </div>

                    {/* Thông tin nhân viên */}
                    <div style={{ paddingLeft: "8px" }}>
                      <div
                        style={{
                          fontWeight: "700",
                          color: "#111827",
                          fontSize: "14px",
                        }}
                      >
                        {row.ten || "N/A"}
                      </div>
                      <div style={{ fontSize: "12px", color: "#6b7280" }}>
                        Mã NV: {row.ma_nv}
                      </div>
                    </div>

                    {/* Thời điểm phát hiện */}
                    <div style={{ textAlign: "right" }}>
                      <div
                        style={{
                          fontWeight: "600",
                          color: "#111827",
                          fontSize: "13px",
                        }}
                      >
                        {row.gio || row.timestamp?.slice(11, 19)}
                      </div>
                      <div style={{ fontSize: "10px", color: "#9ca3af" }}>
                        {row.ngay || row.timestamp?.slice(0, 10)}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
