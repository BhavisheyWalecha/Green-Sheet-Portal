import { createContext, useContext, useEffect, useState } from "react";
import { Routes, Route, Navigate, Link, useNavigate } from "react-router-dom";
import { api, getToken, setToken, ROLE_LABEL } from "./api.js";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import NewSheet from "./pages/NewSheet.jsx";
import SheetDetail from "./pages/SheetDetail.jsx";
import Admin from "./pages/Admin.jsx";
import Mailbox from "./pages/Mailbox.jsx";

const Auth = createContext(null);
export const useAuth = () => useContext(Auth);

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    if (!getToken()) return setReady(true);
    api("/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, []);

  const login = (token, u) => { setToken(token); setUser(u); nav("/"); };
  const logout = () => { setToken(null); setUser(null); nav("/login"); };
  if (!ready) return <div className="center muted">Loading...</div>;

  return (
    <Auth.Provider value={{ user, login, logout }}>
      {user && (
        <header className="topbar">
          <Link to="/" className="brand">Green Sheet Portal</Link>
          <nav>
            <Link to="/">Dashboard</Link>
            {["club_secretary", "club_joint_secretary"].includes(user.role) && <Link to="/new">New sheet</Link>}
            <Link to="/mailbox">Notifications</Link>
            {user.role === "admin" && <Link to="/admin">Admin</Link>}
          </nav>
          <div className="who">
            <div><b>{user.name}</b></div>
            <div className="muted small">{user.designation || ROLE_LABEL[user.role]}{user.club_name ? ` - ${user.club_name}` : ""}</div>
          </div>
          <button className="ghost" onClick={logout}>Sign out</button>
        </header>
      )}
      <main className="container">
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
          <Route path="/" element={user ? <Dashboard /> : <Navigate to="/login" />} />
          <Route path="/new" element={user ? <NewSheet /> : <Navigate to="/login" />} />
          <Route path="/sheets/:id" element={user ? <SheetDetail /> : <Navigate to="/login" />} />
          <Route path="/mailbox" element={user ? <Mailbox /> : <Navigate to="/login" />} />
          <Route path="/admin" element={user?.role === "admin" ? <Admin /> : <Navigate to="/" />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </Auth.Provider>
  );
}
