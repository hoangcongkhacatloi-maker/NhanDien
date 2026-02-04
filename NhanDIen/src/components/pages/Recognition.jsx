import { useState, useEffect } from "react";
import "../css/Recognition.css";

// Thay đổi URL này cho đúng với Backend của bạn
const BACKEND_URL = "http://localhost:8000";

export default function Recognition() {
  const [aiEnabled, setAiEnabled] = useState(false);
  const [filters, setFilters] = useState({ from: "", to: "", employee: "" });
  const [data, setData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [hoverRecord, setHoverRecord] = useState(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });

  // 1. Quản lý AI (Bật khi vào trang, tắt khi thoát trang)
  useEffect(() => {
    // VÀO TRANG → BẬT AI
    fetch(`${BACKEND_URL}/ai/enable`, { method: "POST" })
      .then(() => setAiEnabled(true))
      .catch((err) => console.error("Không thể kết nối Backend:", err));

    // Tải dữ liệu lần đầu
    loadHistory();

    // Tự động làm mới lịch sử mỗi 3 giây
    const interval = setInterval(loadHistory, 3000);

    return () => {
      clearInterval(interval);
      // THOÁT TRANG → TẮT AI
      fetch(`${BACKEND_URL}/ai/disable`, { method: "POST" }).catch(() => {});
    };
  }, []);

  // 2. Hàm tải lịch sử từ Backend
  const loadHistory = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/timekeeping/history`);
      const records = await res.json();
      if (Array.isArray(records)) {
        // Đảo ngược mảng để dữ liệu mới nhất lên đầu
        setData([...records].reverse());
      }
    } catch (err) {
      console.error("Lỗi tải lịch sử:", err);
    }
  };

  // 3. Xử lý Logic Bộ lọc (Filter)
  useEffect(() => {
    let result = [...data];

    if (filters.from)
      result = result.filter(
        (r) => r.thoi_gian && r.thoi_gian.slice(0, 10) >= filters.from
      );

    if (filters.to)
      result = result.filter(
        (r) => r.thoi_gian && r.thoi_gian.slice(0, 10) <= filters.to
      );

    if (filters.employee) {
      const q = filters.employee.toLowerCase();
      result = result.filter(
        (r) =>
          (r.ten && r.ten.toLowerCase().includes(q)) ||
          (r.ma_nv && r.ma_nv.toLowerCase().includes(q))
      );
    }

    setFilteredData(result);
  }, [filters, data]);

  // 4. Các hàm bổ trợ (Helper)
  const showTime = (record) => {
    if (!record?.thoi_gian) return "";
    return record.thoi_gian.replace("T", " ");
  };

  const photoUrl = (record) => {
    if (!record?.photo_path) return null;
    return `${BACKEND_URL}/photo?path=${encodeURIComponent(record.photo_path)}`;
  };

  const daysWithViolations = new Set(
    data
      .filter((r) => r.photo_path && r.photo_path.includes("exit_"))
      .map((r) => r.thoi_gian?.slice(0, 10))
  );

  return (
    <div className="recognition">
      {/* HEADER */}
      <div className="page-header">
        <h1>👁 Giám sát nhận diện AI</h1>
        <div className={`ai-status ${aiEnabled ? "on" : "off"}`}>
          <span className="dot"></span>
          {aiEnabled ? "AI đang hoạt động" : "AI đang khởi động..."}
        </div>
      </div>

      <div className="recognition-layout">
        {/* PANEL TRÁI: CAMERA TRỰC TIẾP */}
        <div className="panel left-panel">
          <div className="card">
            <div className="card-title">📷 Camera trực tiếp</div>
            <div className="video-container">
              <img src={`${BACKEND_URL}/video`} className="camera" alt="Live Camera" />
            </div>
            <div className="hint-box">
              <p><strong>Thông báo:</strong> Hệ thống đang quét khuôn mặt thời gian thực. Dữ liệu sẽ tự động cập nhật vào bảng bên phải.</p>
            </div>
          </div>
        </div>

        {/* PANEL PHẢI: LỊCH SỬ CHẤM CÔNG */}
        <div className="panel right-panel">
          <div className="card">
            <div className="card-title">📋 Lịch sử ghi nhận</div>

            {/* THANH BỘ LỌC */}
            <div className="filter-bar">
              <div className="filter-group">
                <input
                  type="date"
                  value={filters.from}
                  onChange={(e) => setFilters({ ...filters, from: e.target.value })}
                  title="Từ ngày"
                />
                <span>→</span>
                <input
                  type="date"
                  value={filters.to}
                  onChange={(e) => setFilters({ ...filters, to: e.target.value })}
                  title="Đến ngày"
                />
              </div>
              <input
                className="search-input"
                placeholder="Tìm tên hoặc mã nhân viên..."
                value={filters.employee}
                onChange={(e) => setFilters({ ...filters, employee: e.target.value })}
              />
              <button className="btn-refresh" onClick={loadHistory} title="Làm mới">
                🔄
              </button>
            </div>

            {/* BẢNG DỮ LIỆU */}
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Thời gian</th>
                    <th>Nhân viên</th>
                    <th>Mã NV</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredData.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="empty-row">Không tìm thấy dữ liệu chấm công</td>
                    </tr>
                  ) : (
                    filteredData.map((row, i) => {
                      const isViolationDay = daysWithViolations.has(row.thoi_gian?.slice(0, 10));
                      const isExit = row.photo_path?.includes("exit_");

                      return (
                        <tr
                          key={i}
                          className={`${isViolationDay ? "violation-row" : ""} ${isExit ? "exit-entry" : ""}`}
                          onMouseEnter={(e) => {
                            setHoverRecord(row);
                            setHoverPos({ x: e.clientX, y: e.clientY });
                          }}
                          onMouseLeave={() => setHoverRecord(null)}
                        >
                          <td>{showTime(row)}</td>
                          <td><strong>{row.ten}</strong></td>
                          <td><code>{row.ma_nv}</code></td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* ẢNH PREVIEW KHI RÊ CHUỘT (HOVER) */}
      {hoverRecord && photoUrl(hoverRecord) && (
        <div
          className="hover-card"
          style={{ 
            left: hoverPos.x + 20, 
            top: Math.min(hoverPos.y, window.innerHeight - 250) // Chống tràn màn hình phía dưới
          }}
        >
          <div className="hover-header">
            <span>{hoverRecord.ten}</span>
            <small>{showTime(hoverRecord)}</small>
          </div>
          <img src={photoUrl(hoverRecord)} alt="Snapshot" />
        </div>
      )}
    </div>
  );
}