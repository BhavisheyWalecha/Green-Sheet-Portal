import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt, ROLE_LABEL } from "../api.js";
import { useAuth } from "../App.jsx";
import { StatusBadge, Alert } from "../components/Bits.jsx";

function Table({ rows, empty }) {
  if (!rows.length) return <p className="muted">{empty}</p>;
  return (
    <table>
      <thead><tr><th>Ref</th><th>Event</th><th>Club</th><th>Event date</th><th>Status</th><th>With</th><th>Updated</th></tr></thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.id}>
            <td><Link to={`/sheets/${s.id}`}>{s.ref}</Link></td><td>{s.title}</td><td>{s.club.name}</td><td>{s.event_date}</td>
            <td><StatusBadge status={s.status} /></td><td>{s.current_approver?.name || "-"}</td><td className="small">{fmt(s.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [sheets, setSheets] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/sheets").then(setSheets).catch((e) => setErr(e.message)); }, []);
  if (err) return <Alert>{err}</Alert>;
  if (!sheets) return <p className="muted">Loading...</p>;

  const by = (...st) => sheets.filter((s) => st.includes(s.status));
  const isClub = user.role.startsWith("club_");
  const isAuth = ["approver", "dean_sw"].includes(user.role);
  const mine = sheets.filter((s) => s.status === "pending" && s.current_approver?.id === user.id);

  return (
    <>
      <div className="row between">
        <div><h1>{ROLE_LABEL[user.role]} dashboard</h1><p className="muted">Welcome, {user.name}.</p></div>
        {isClub && <Link to="/new" className="btn">+ New green sheet</Link>}
      </div>

      {isClub && (
        <>
          <div className="stats">
            <div className="stat"><b>{by("pending").length}</b><span>In approval</span></div>
            <div className="stat warn"><b>{by("changes_requested", "blocked").length}</b><span>Need your action</span></div>
            <div className="stat ok"><b>{by("ready").length}</b><span>Ready to collect at DSW</span></div>
            <div className="stat"><b>{by("collected").length}</b><span>Completed</span></div>
          </div>
          <h2>Needs your action</h2>
          <Table rows={by("changes_requested", "blocked")} empty="Nothing waiting on you." />
          <h2>All green sheets of {user.club_name}</h2>
          <Table rows={sheets} empty="No green sheets yet. Create your first one." />
        </>
      )}

      {isAuth && (
        <>
          <div className="stats">
            <div className="stat warn"><b>{mine.length}</b><span>Waiting for you</span></div>
            <div className="stat"><b>{by("pending").length - mine.length}</b><span>Elsewhere in approval</span></div>
            <div className="stat ok"><b>{by("approved", "ready", "collected").length}</b><span>Fully approved</span></div>
          </div>
          <h2>Waiting for your signature</h2>
          <Table rows={mine} empty="You're all caught up." />
          <h2>{user.role === "dean_sw" ? "All sheets" : "Sheets you handled"}</h2>
          <Table rows={sheets.filter((s) => !mine.includes(s))} empty="Nothing yet." />
        </>
      )}

      {user.role === "dsw_office" && (
        <>
          <div className="stats">
            <div className="stat warn"><b>{by("approved").length}</b><span>To print & stamp</span></div>
            <div className="stat ok"><b>{by("ready").length}</b><span>Awaiting collection</span></div>
            <div className="stat"><b>{by("collected").length}</b><span>Collected</span></div>
          </div>
          <h2>To print & stamp</h2><Table rows={by("approved")} empty="No sheets waiting." />
          <h2>Ready for collection</h2><Table rows={by("ready")} empty="None." />
          <h2>Collected</h2><Table rows={by("collected")} empty="None yet." />
        </>
      )}

      {user.role === "admin" && (<><h2>All green sheets</h2><Table rows={sheets} empty="None yet." /></>)}
    </>
  );
}
