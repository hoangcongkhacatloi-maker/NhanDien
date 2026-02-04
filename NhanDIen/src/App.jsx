import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Recognition from "./components/pages/Recognition";
import Capture from "./components/pages/Capture";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/" element={<Recognition />} />
            <Route path="/capture" element={<Capture />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}