import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt } from "../api.js";

export default function Mailbox() {
  const [mails, setMails] = useState(null);
  const [open, setOpen] = useState(null);
  useEffect(() => { api("/emails").then(setMails); }, []);
  if (!mails) return <p className="muted">Loading...</p>;
  return (
    <>
      <h1>Notifications</h1>
      <p className="muted">Every update is also emailed to the club mailbox, the people involved and the cc list.</p>
      {!mails.length && <p className="muted">No notifications yet.</p>}
      {mails.map((m) => (
        <div key={m.id} className="card mail" onClick={() => setOpen(open === m.id ? null : m.id)}>
          <div className="row between"><b>{m.subject}</b><span className="muted small">{fmt(m.at)}</span></div>
          <div className="muted small">to {m.to} {m.delivered ? "· sent via SMTP" : "· logged only (no SMTP reachable)"}</div>
          {open === m.id && <><pre>{m.body}</pre>{m.sheet_id && <Link to={`/sheets/${m.sheet_id}`}>Open sheet</Link>}</>}
        </div>
      ))}
    </>
  );
}
