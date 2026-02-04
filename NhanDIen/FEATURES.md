# Tính năng mới - Hệ thống Chấm công

## 📋 Tổng quan

Đã thêm 3 tính năng chính vào hệ thống chấm công:

### 1. ⏰ Quản lý thời gian cho phép chấm công

**Vị trí:** Trang "Hệ thống nhận diện" (Recognition)

**Chức năng:**
- Cấu hình các khung giờ cho phép chấm công (mặc định: 7:00-9:00 và 17:00-19:00)
- Thêm/xóa nhiều khung giờ tùy ý
- Lưu cấu hình vào file `backend/ChamCong/TimekeepingConfig.json`

**Cách sử dụng:**
1. Vào trang "Hệ thống nhận diện"
2. Ở panel bên phải, chỉnh sửa các khung giờ
3. Nhấn "Thêm khung giờ" để thêm khung giờ mới
4. Nhấn "Lưu cấu hình" để áp dụng

### 2. 📊 Xem lịch sử chấm công

**Vị trí:** Trang "Lịch sử chấm công" (Timekeeping History)

**Chức năng:**
- Hiển thị toàn bộ lịch sử chấm công từ file JSON
- Lọc theo ngày (từ ngày - đến ngày)
- Tìm kiếm theo tên hoặc mã nhân viên
- Hiển thị trạng thái: Đã duyệt / Chờ duyệt / Từ chối

**Cách sử dụng:**
1. Vào trang "Lịch sử chấm công"
2. Chọn khoảng thời gian hoặc nhập tên nhân viên
3. Nhấn "Tìm" để lọc dữ liệu

### 3. ✅ Duyệt chấm công ngoài giờ

**Vị trí:** Trang "Lịch sử chấm công" (Timekeeping History)

**Chức năng:**
- Tự động phát hiện chấm công ngoài khung giờ cho phép
- Đánh dấu trạng thái "Chờ duyệt" (màu vàng)
- Cho phép quản lý duyệt hoặc từ chối với lý do
- Lưu lại quyết định vào file JSON

**Cách sử dụng:**
1. Vào trang "Lịch sử chấm công"
2. Tìm các bản ghi có trạng thái "Chờ duyệt"
3. Nhấn nút "⚙️ Duyệt"
4. Nhập lý do (nếu cần)
5. Chọn "✅ Duyệt" hoặc "❌ Từ chối"

## 🔧 API Endpoints mới

### Backend APIs:

```
GET  /api/timekeeping/config          - Lấy cấu hình thời gian
POST /api/timekeeping/config          - Cập nhật cấu hình thời gian
GET  /api/timekeeping/history         - Lấy lịch sử chấm công
POST /api/timekeeping/approve/{index} - Duyệt/từ chối chấm công
GET  /api/employees                   - Lấy danh sách nhân viên
```

## 📁 Cấu trúc dữ liệu

### File: `backend/ChamCong/ChamCong.json`
```json
[
  {
    "ten": "Kha",
    "ma_nv": "a6",
    "ngay": "2026-01-31",
    "gio": "08:30:00",
    "status": "approved",
    "reason": "",
    "photo_path": "/path/to/photo.jpg"
  },
  {
    "ten": "Duyen",
    "ma_nv": "a5",
    "ngay": "2026-01-31",
    "gio": "22:15:00",
    "status": "pending",
    "reason": "",
    "photo_path": "/path/to/photo.jpg"
  }
]
```

### File: `backend/ChamCong/TimekeepingConfig.json`
```json
{
  "allowed_times": [
    { "from": "07:00", "to": "09:00" },
    { "from": "17:00", "to": "19:00" }
  ]
}
```

## 🎨 Trạng thái chấm công

| Trạng thái | Màu sắc | Ý nghĩa |
|-----------|---------|---------|
| `approved` | Xanh lá | Đã được duyệt (hoặc trong giờ cho phép) |
| `pending` | Vàng | Chờ quản lý duyệt (ngoài giờ) |
| `rejected` | Đỏ | Đã bị từ chối |

## 🚀 Cách hoạt động

1. **Khi nhân viên chấm công:**
   - Hệ thống kiểm tra giờ hiện tại
   - Nếu trong khung giờ cho phép → `status: "approved"`
   - Nếu ngoài khung giờ → `status: "pending"`

2. **Quản lý duyệt:**
   - Vào trang lịch sử
   - Xem các bản ghi "Chờ duyệt"
   - Duyệt → `status: "approved"`
   - Từ chối → `status: "rejected"`

## 📝 Ghi chú

- File cấu hình sẽ tự động tạo nếu chưa tồn tại
- Mặc định cho phép chấm công: 7:00-9:00 và 17:00-19:00
- Có thể thêm nhiều khung giờ tùy ý (ví dụ: ca đêm, ca trưa)
- Lịch sử chấm công được lưu vĩnh viễn trong file JSON
