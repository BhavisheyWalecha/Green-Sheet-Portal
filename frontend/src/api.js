const KEY = "gs_token";
export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY));

export async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;
  const res = await fetch(`/api${path}`, { method, headers, body });
  if (res.status === 401 && path !== "/auth/login") { setToken(null); window.location.href = "/login"; throw new Error("Session expired"); }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = await res.json();
      msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

export async function openPdf(path) {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error("Could not load the PDF");
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
}

export const fmt = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");
export const ROLE_LABEL = {
  club_secretary: "Club Secretary", club_joint_secretary: "Club Joint Secretary", approver: "Approving Authority",
  dean_sw: "Dean of Student Welfare", dsw_office: "DSW Office", admin: "Administrator",
};
export const STATUS_LABEL = {
  blocked: "Blocked by AI", pending: "Awaiting approval", changes_requested: "Changes requested", rejected: "Rejected",
  revoked: "Revoked", approved: "Approved - at DSW office", ready: "Ready to collect", collected: "Collected",
};
