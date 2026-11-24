import { useEffect, useState } from "react";
import { api, ROLE_LABEL } from "../api.js";
import { Alert } from "../components/Bits.jsx";

function Users({ clubs }) {
  const [users, setUsers] = useState([]);
  const [f, setF] = useState({ name: "", email: "", password: "", role: "club_secretary", designation: "", club_id: "" });
  const [err, setErr] = useState("");
  const load = () => api("/admin/users").then(setUsers);
  useEffect(() => { load(); }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const isClub = f.role.startsWith("club_");
  async function add(e) {
    e.preventDefault(); setErr("");
    try { await api("/admin/users", { method: "POST", json: { ...f, club_id: isClub ? Number(f.club_id) : null } }); setF({ ...f, name: "", email: "", password: "" }); load(); }
    catch (x) { setErr(x.message); }
  }
  const toggle = (u) => api(`/admin/users/${u.id}`, { method: "PATCH", json: { active: !u.active } }).then(load).catch((x) => setErr(x.message));
  return (
    <>
      <h2>Users</h2>
      <form className="card" onSubmit={add}>
        <div className="row">
          <label className="grow">Name<input value={f.name} onChange={set("name")} required /></label>
          <label className="grow">Email<input type="email" value={f.email} onChange={set("email")} required placeholder={isClub ? "name@clubs.college.edu" : "name@college.edu"} /></label>
          <label className="grow">Password<input type="password" minLength={8} value={f.password} onChange={set("password")} required /></label>
        </div>
        <div className="row">
          <label className="grow">Role<select value={f.role} onChange={set("role")}>{Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="grow">Designation<input value={f.designation} onChange={set("designation")} placeholder="e.g. Faculty Coordinator - Chess Club" /></label>
          {isClub && <label className="grow">Club<select value={f.club_id} onChange={set("club_id")} required><option value="">Select...</option>{clubs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}
        </div>
        <Alert>{err}</Alert>
        <button>Add user</button>
      </form>
      <table>
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Designation / club</th><th>Status</th><th /></tr></thead>
        <tbody>{users.map((u) => (
          <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{ROLE_LABEL[u.role]}</td><td>{u.club_name || u.designation}</td>
            <td>{u.active ? "Active" : "Disabled"}</td><td><button className="link" onClick={() => toggle(u)}>{u.active ? "Disable" : "Enable"}</button></td></tr>
        ))}</tbody>
      </table>
    </>
  );
}

function Clubs({ clubs, reload }) {
  const [approvers, setApprovers] = useState([]);
  const [f, setF] = useState({ name: "", email: "" });
  const [err, setErr] = useState("");
  useEffect(() => { api("/approvers").then(setApprovers); }, []);
  async function add(e) {
    e.preventDefault(); setErr("");
    try { await api("/admin/clubs", { method: "POST", json: { ...f, cc_emails: [], suggested_path: [] } }); setF({ name: "", email: "" }); reload(); }
    catch (x) { setErr(x.message); }
  }
  async function save(c, cc, path) {
    setErr("");
    try {
      await api(`/admin/clubs/${c.id}`, { method: "PATCH", json: { name: c.name, email: c.email, cc_emails: cc.split(",").map((x) => x.trim()).filter(Boolean), suggested_path: path } });
      reload();
    } catch (x) { setErr(x.message); }
  }
  return (
    <>
      <h2>Clubs</h2>
      <form className="card" onSubmit={add}>
        <div className="row">
          <label className="grow">Club name<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></label>
          <label className="grow">Club mailbox<input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required placeholder="chess@clubs.college.edu" /></label>
        </div>
        <button>Add club</button>
      </form>
      <Alert>{err}</Alert>
      {clubs.map((c) => <ClubRow key={c.id} club={c} approvers={approvers} save={save} />)}
    </>
  );
}

function ClubRow({ club, approvers, save }) {
  const [cc, setCc] = useState((club.cc_emails || []).join(", "));
  const [path, setPath] = useState(club.suggested_path || []);
  const name = (id) => approvers.find((a) => a.id === id)?.name || `#${id}`;
  return (
    <div className="card">
      <b>{club.name}</b> <span className="muted small">{club.email}</span>
      <label>Also notify (comma-separated emails)<input value={cc} onChange={(e) => setCc(e.target.value)} /></label>
      <div className="small muted">Usual approval path (only a suggestion - each approver still chooses the next step):</div>
      <div className="chips">
        {path.map((id, i) => <span key={i} className="chip">{i + 1}. {name(id)} <button type="button" className="link" onClick={() => setPath(path.filter((_, j) => j !== i))}>✕</button></span>)}
        <select value="" onChange={(e) => e.target.value && setPath([...path, Number(e.target.value)])}>
          <option value="">+ add step</option>{approvers.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>
      <button className="ghost" onClick={() => save(club, cc, path)}>Save</button>
    </div>
  );
}

export default function Admin() {
  const [clubs, setClubs] = useState([]);
  const reload = () => api("/clubs").then(setClubs);
  useEffect(() => { reload(); }, []);
  return <><h1>Administration</h1><Users clubs={clubs} /><Clubs clubs={clubs} reload={reload} /></>;
}
