import { NavLink } from "react-router-dom";
import "./css/Sidebar.css";

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">🤖 AI Cam</h2>

      <nav className="sidebar-nav">
        <NavLink to="/" end>👁 Nhận diện</NavLink>
        <NavLink to="/capture">📸 Chụp ảnh</NavLink>
      </nav>

      <div className="sidebar-footer">Version 2.0</div>
    </aside>
  );
}