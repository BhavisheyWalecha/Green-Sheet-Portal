import { fmt } from "../api.js";

const ICON = { approved: "✓", pending: "…", changes_requested: "↺", rejected: "✕", skipped: "–" };

/** Shows the exact route the sheet has taken, each approver, and what comes next. */
export default function PathTimeline({ sheet }) {
  const nodes = [
    { key: "club", state: "approved", title: sheet.club.name, sub: `Submitted by ${sheet.created_by.name}`, when: sheet.created_at, icon: "★" },
    ...sheet.steps.map((s) => ({
      key: s.id, state: s.status, title: s.approver.name, sub: s.approver.designation, when: s.acted_at || s.created_at,
      note: s.comment, tag: `v${s.version}`, sig: s.signature, icon: ICON[s.status],
      extra: s.status === "approved" ? (s.next_kind === "final" ? "Gave final approval" : "Signed & forwarded") : null,
    })),
  ];
  const done = ["approved", "ready", "collected"].includes(sheet.status);
  nodes.push({
    key: "dsw", state: sheet.status === "collected" ? "approved" : sheet.status === "ready" ? "pending" : done ? "pending" : "future",
    title: "DSW Office", icon: sheet.status === "collected" ? "✓" : "⌂",
    sub: sheet.status === "collected" ? "Collected by the club" : sheet.status === "ready" ? "Stamped - collect your sheet from the DSW office"
      : done ? "Printing and stamping" : "Print, stamp & hand over (final step)",
  });
  return (
    <ol className="path">
      {nodes.map((n) => (
        <li key={n.key} className={`node ${n.state}`}>
          <span className="dot">{n.icon}</span>
          <div className="body">
            <div className="ttl">{n.title} {n.tag && <span className="tag">{n.tag}</span>}</div>
            <div className="muted small">{n.sub}</div>
            {n.extra && <div className="small ok">{n.extra}{n.when ? ` - ${fmt(n.when)}` : ""}</div>}
            {n.state === "pending" && n.key !== "dsw" && <div className="small warn">Waiting for this person</div>}
            {n.state === "changes_requested" && <div className="small warn">Asked for changes - {fmt(n.when)}</div>}
            {n.state === "rejected" && <div className="small bad">Rejected - {fmt(n.when)}</div>}
            {n.note && <div className="note">“{n.note}”</div>}
            {n.sig && <div className="sig">e-sign {n.sig}</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}
