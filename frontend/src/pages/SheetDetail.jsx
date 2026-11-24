import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, openPdf, fmt } from "../api.js";
import { StatusBadge, Alert } from "../components/Bits.jsx";
import PathTimeline from "../components/PathTimeline.jsx";

function ApproverPanel({ sheet, reload }) {
  const [approvers, setApprovers] = useState([]);
  const [comment, setComment] = useState("");
  const [mode, setMode] = useState("forward");
  const [next, setNext] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/approvers").then(setApprovers); }, []);
  const sugg = sheet.suggested_path.map((u) => u.id);
  const signed = sheet.steps.filter((s) => s.status === "approved").map((s) => s.approver.id);
  const nextSuggested = sugg.find((id) => !signed.includes(id) && approvers.some((a) => a.id === id));
  useEffect(() => { if (nextSuggested && !next) setNext(String(nextSuggested)); }, [nextSuggested]); // eslint-disable-line

  async function send(decision) {
    setErr("");
    const json = { decision, comment };
    if (decision === "approve") {
      if (mode === "final") json.next_kind = "final";
      else { if (!next) return setErr("Choose who should sign next"); json.next_kind = "approver"; json.next_approver_id = Number(next); }
    }
    if (decision !== "approve" && !comment.trim()) return setErr("Add a comment explaining what to change / why");
    if (decision === "reject" && !confirm("Reject this green sheet? The club will have to start over.")) return;
    setBusy(true);
    try { await api(`/sheets/${sheet.id}/action`, { method: "POST", json }); setComment(""); await reload(); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="card action">
      <h3>Your decision</h3>
      <label>Comment {mode === "forward" ? "(optional when approving; required to request changes)" : ""}
        <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="e.g. Please attach the sponsor's letter on page 2" />
      </label>
      <fieldset>
        <legend>If you approve, what happens next?</legend>
        <label className="radio"><input type="radio" checked={mode === "forward"} onChange={() => setMode("forward")} /> Forward to another authority</label>
        {mode === "forward" && (
          <select value={next} onChange={(e) => setNext(e.target.value)}>
            <option value="">Choose next approver...</option>
            {approvers.map((a) => <option key={a.id} value={a.id}>{a.name} - {a.designation}{a.id === nextSuggested ? " (suggested)" : ""}</option>)}
          </select>
        )}
        {sheet.can.finalize && <label className="radio"><input type="radio" checked={mode === "final"} onChange={() => setMode("final")} /> Final approval - send to DSW office for print & stamp</label>}
      </fieldset>
      <Alert>{err}</Alert>
      <div className="row">
        <button disabled={busy} onClick={() => send("approve")}>✓ Approve & e-sign</button>
        <button disabled={busy} className="warnbtn" onClick={() => send("changes")}>↺ Request changes</button>
        <button disabled={busy} className="danger" onClick={() => send("reject")}>✕ Reject</button>
      </div>
    </div>
  );
}

function ClubPanel({ sheet, reload }) {
  const [approvers, setApprovers] = useState([]);
  const [file, setFile] = useState(null);
  const [desc, setDesc] = useState(sheet.description);
  const [first, setFirst] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (sheet.can.resubmit) api("/approvers").then(setApprovers); }, [sheet.can.resubmit]);

  async function resubmit(e) {
    e.preventDefault(); setErr("");
    const form = new FormData();
    form.append("description", desc);
    if (file) form.append("file", file);
    if (sheet.needs_first_approver) form.append("first_approver_id", first);
    setBusy(true);
    try { await api(`/sheets/${sheet.id}/resubmit`, { method: "POST", form }); setFile(null); await reload(); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  }
  async function revoke() {
    if (!confirm("Revoke this green sheet? It will be withdrawn from the approver.")) return;
    try { await api(`/sheets/${sheet.id}/revoke`, { method: "POST" }); await reload(); } catch (x) { setErr(x.message); }
  }
  return (
    <>
      {sheet.can.resubmit && (
        <form className="card action" onSubmit={resubmit}>
          <h3>{sheet.status === "blocked" ? "Fix and resubmit" : "Make the requested changes"}</h3>
          {sheet.status === "changes_requested" && <p className="muted small">After you resubmit it returns to the approver who asked for the change.</p>}
          <label>Description<textarea rows={4} value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
          <label>Corrected PDF {sheet.status === "blocked" ? "(required)" : "(optional)"}<input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0])} required={sheet.status === "blocked"} /></label>
          {sheet.needs_first_approver && (
            <label>First approver
              <select value={first} onChange={(e) => setFirst(e.target.value)} required>
                <option value="">Select...</option>{approvers.map((a) => <option key={a.id} value={a.id}>{a.name} - {a.designation}</option>)}
              </select>
            </label>
          )}
          <Alert>{err}</Alert>
          <button disabled={busy}>{busy ? "Checking..." : "Resubmit"}</button>
        </form>
      )}
      {sheet.can.revoke && <div className="card action"><h3>Withdraw</h3><p className="muted small">You can revoke until the Dean gives final approval.</p><Alert>{err}</Alert><button className="danger" onClick={revoke}>Revoke this sheet</button></div>}
    </>
  );
}

function DswPanel({ sheet, reload }) {
  const [err, setErr] = useState("");
  const go = (p) => async () => { try { await api(`/sheets/${sheet.id}/dsw/${p}`, { method: "POST" }); await reload(); } catch (x) { setErr(x.message); } };
  return (
    <div className="card action">
      <h3>DSW office</h3>
      {sheet.can.stamp && <><p className="muted small">1. Download the print copy (includes the approval trail page). 2. Print and stamp it. 3. Mark it ready - the club is emailed.</p>
        <div className="row"><button className="ghost" onClick={() => openPdf(`/sheets/${sheet.id}/file`)}>Open print copy</button><button onClick={go("stamp")}>Printed & stamped - ready to collect</button></div></>}
      {sheet.can.collect && <button onClick={go("collected")}>Club collected the sheet</button>}
      <Alert>{err}</Alert>
    </div>
  );
}

export default function SheetDetail() {
  const { id } = useParams();
  const [sheet, setSheet] = useState(null);
  const [err, setErr] = useState("");
  const reload = useCallback(() => api(`/sheets/${id}`).then(setSheet).catch((e) => setErr(e.message)), [id]);
  useEffect(() => { reload(); }, [reload]);
  if (err) return <Alert>{err}</Alert>;
  if (!sheet) return <p className="muted">Loading...</p>;
  const flags = sheet.ai.flags;
  return (
    <>
      <div className="row between">
        <div>
          <div className="muted small">{sheet.ref} - v{sheet.version}</div>
          <h1>{sheet.title}</h1>
          <p className="muted">{sheet.club.name} - {sheet.event_date} - {sheet.venue || "venue TBA"}</p>
        </div>
        <StatusBadge status={sheet.status} />
      </div>

      <div className="grid">
        <div>
          <div className="card"><h3>Description</h3><p className="pre">{sheet.description}</p>
            <div className="row">
              <button className="ghost" onClick={() => openPdf(`/sheets/${sheet.id}/file`)}>View signed PDF</button>
              <button className="ghost" onClick={() => openPdf(`/sheets/${sheet.id}/file?plain=true`)}>View original upload</button>
            </div>
            <p className={`small ${sheet.integrity_ok ? "ok" : "bad"}`}>{sheet.integrity_ok ? `✓ ${sheet.signatures} e-signature(s) verified, trail untampered` : "⚠ Signature chain failed verification"}</p>
          </div>

          {sheet.can.act && <ApproverPanel sheet={sheet} reload={reload} />}
          <ClubPanel sheet={sheet} reload={reload} />
          {(sheet.can.stamp || sheet.can.collect) && <DswPanel sheet={sheet} reload={reload} />}

          <div className="card">
            <h3>AI check <span className={`badge ai-${sheet.ai.status}`}>{sheet.ai.status === "pass" ? "Passed" : sheet.ai.status === "warn" ? "Passed with notes" : "Blocked"}</span></h3>
            <p><b>Summary:</b> {sheet.ai.summary}</p>
            {flags.length > 0 ? <ul className="flags">{flags.map((f, i) => <li key={i} className={f.level}>{f.msg}</li>)}</ul> : <p className="ok small">No problems found.</p>}
            <p className="muted small">Checked by: {sheet.ai.engine}</p>
          </div>
        </div>

        <div>
          <div className="card"><h3>Approval path</h3><PathTimeline sheet={sheet} /></div>
          <div className="card"><h3>Activity</h3>
            <ul className="events">{[...sheet.events].reverse().map((e, i) => <li key={i}><b>{e.action.replace(/_/g, " ")}</b>{e.actor ? ` - ${e.actor.name}` : " - system"}<div className="muted small">{fmt(e.at)}{e.detail ? ` - ${e.detail}` : ""}</div></li>)}</ul>
          </div>
        </div>
      </div>
    </>
  );
}
