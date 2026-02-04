import { useState, useEffect } from "react";
import "../css/TimekeepingHistory.css";

function getEventKey(record) {
  if (record.photo_path && record.photo_path.includes("exit_")) {
    return "unauthorized_exit";
  }
  return "attendance_on_time";
}

function showTime(record) {
  if (!record?.thoi_gian) return "";
  return record.thoi_gian.replace("T", " ");
}

export default function TimekeepingHistory() {
  const [filters, setFilters] = useState({ from: "", to: "", employee: "" });
  const [data, setData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [hoverRecord, setHoverRecord] = useState(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    loadHistory();
  }, []);

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

  const loadHistory = async () => {
    try {
      const res = await fetch("/api/timekeeping/history");
      const records = await res.json();
      setData(Array.isArray(records) ? records : []);
    } catch (err) {
      console.error("Lỗi tải lịch sử:", err);
    }
  };

  const daysWithViolations = new Set(
    data
      .filter((r) => r.photo_path && r.photo_path.includes("exit_"))
      .map((r) => r.thoi_gian?.slice(0, 10))
  );

  const photoUrl = (record) => {
    if (!record.photo_path) return null;
    return `/api/photo?path=${encodeURIComponent(record.photo_path)}`;
  };

  return (
    <div className="timekeeping">
      <h1>📋 Lịch sử chấm công</h1>

      {/* FILTER */}
      <div className="filter-bar">
        <div className="filter-item">
          <label>📅 Từ ngày</label>
          <input
            type="date"
            value={filters.from}
            onChange={(e) => setFilters({ ...filters, from: e.target.value })}
          />
        </div>
        <div className="filter-item">
          <label>📅 Đến ngày</label>
          <input
            type="date"
            value={filters.to}
            onChange={(e) => setFilters({ ...filters, to: e.target.value })}
          />
        </div>
        <div className="filter-item">
          <label>👤 Nhân viên</label>
          <input
            placeholder="Tên hoặc mã NV"
            value={filters.employee}
            onChange={(e) =>
              setFilters({ ...filters, employee: e.target.value })
            }
          />
        </div>
        <div className="filter-item action">
          <label>&nbsp;</label>
          <button className="btn-search" onClick={loadHistory}>
            🔍 Tải lại
          </button>
        </div>
      </div>

      {/* TABLE */}
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Nhân viên</th>
              <th>Mã NV</th>
              <th>Ghi chú</th>
            </tr>
          </thead>

          <tbody>
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan="5" className="empty-row">
                  Chưa có dữ liệu chấm công
                </td>
              </tr>
            ) : (
              filteredData.map((row, i) => {
                const key = getEventKey(row);
                const isViolationDay = daysWithViolations.has(
                  row.thoi_gian?.slice(0, 10)
                );

                return (
                  <tr
                    key={i}
                    className={isViolationDay ? "row-violation-day" : ""}
                    onMouseEnter={(e) => {
                      setHoverRecord(row);
                      setHoverPos({ x: e.clientX, y: e.clientY });
                    }}
                    onMouseLeave={() => setHoverRecord(null)}
                  >
                    <td>{showTime(row)}</td>
                    <td>{row.ten}</td>
                    <td>{row.ma_nv}</td>
                    <td>
                      {row.photo_path?.includes("exit_")
                        ? "Tự ý ra ngoài"
                        : "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* HOVER */}
      {hoverRecord && (
        <div
          className="hover-card"
          style={{ left: hoverPos.x + 16, top: hoverPos.y + 8 }}
        >
          <div className="hover-card-time">
            {showTime(hoverRecord)}
          </div>
          {photoUrl(hoverRecord) && (
            <img
              src={photoUrl(hoverRecord)}
              alt="Chấm công"
              className="hover-card-photo"
            />
          )}
        </div>
      )}
    </div>
  );
}