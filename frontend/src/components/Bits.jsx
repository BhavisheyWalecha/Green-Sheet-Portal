import { STATUS_LABEL } from "../api.js";

export function StatusBadge({ status }) {
  return <span className={`badge s-${status}`}>{STATUS_LABEL[status] || status}</span>;
}

export function Alert({ kind = "error", children }) {
  if (!children) return null;
  return <div className={`alert ${kind}`}>{children}</div>;
}
