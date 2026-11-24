import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../App.jsx";
import { Alert } from "../components/Bits.jsx";

export default function NewSheet() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [approvers, setApprovers] = useState([]);
  const [suggested, setSuggested] = useState([]);
  const [f, setF] = useState({ title: "", description: "", event_date: "", venue: "", first: "" });
  const [file, setFile] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api("/approvers"), api("/clubs")]).then(([a, c]) => {
      setApprovers(a);
      const club = c.find((x) => x.id === user.club_id);
      setSuggested(club?.suggested_path || []);
      if (club?.suggested_path?.length) setF((p) => ({ ...p, first: String(club.suggested_path[0]) }));
    });
  }, [user.club_id]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault(); setErr("");
    if (!file) return setErr("Attach the green sheet as a PDF");
    const form = new FormData();
    form.append("title", f.title); form.append("description", f.description); form.append("event_date", f.event_date);
    form.append("venue", f.venue); form.append("first_approver_id", f.first); form.append("file", file);
    setBusy(true);
    try { const s = await api("/sheets", { method: "POST", form }); nav(`/sheets/${s.id}`); }
    catch (x) { setErr(x.message); setBusy(false); }
  }
  return (
    <form className="card narrow" onSubmit={submit}>
      <h1>New green sheet</h1>
      <p className="muted">The AI checker summarises and screens the sheet first. If it finds anything malicious it is not sent to any authority.</p>
      <label>Event title<input value={f.title} onChange={set("title")} required maxLength={200} /></label>
      <label>Event description<textarea rows={5} value={f.description} onChange={set("description")} required minLength={30} placeholder="What, who, expected participants, budget, why..." /></label>
      <div className="row">
        <label className="grow">Event date<input type="date" value={f.event_date} onChange={set("event_date")} required /></label>
        <label className="grow">Venue<input value={f.venue} onChange={set("venue")} required /></label>
      </div>
      <label>First approver
        <select value={f.first} onChange={set("first")} required>
          <option value="">Select who signs first...</option>
          {approvers.map((a) => <option key={a.id} value={a.id}>{a.name} - {a.designation}{suggested.includes(a.id) ? " (usual for your club)" : ""}</option>)}
        </select>
      </label>
      <p className="muted small">Each approver decides the next step after signing, so you only choose the first.</p>
      <label>Green sheet (PDF, signed by your club)<input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} required /></label>
      <Alert>{err}</Alert>
      <button disabled={busy}>{busy ? "Checking & submitting..." : "Submit for approval"}</button>
    </form>
  );
}
