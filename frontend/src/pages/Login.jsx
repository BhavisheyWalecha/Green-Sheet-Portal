import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../App.jsx";
import { Alert } from "../components/Bits.jsx";

const DEMO = [
  ["Club secretary", "riya.secretary@clubs.college.edu"], ["Club joint secretary", "karan.joint@clubs.college.edu"],
  ["Faculty coordinator", "arun.kumar@college.edu"], ["HOD", "hod.cse@college.edu"],
  ["Dean Student Welfare", "dean.sw@college.edu"], ["DSW office", "dsw.office@college.edu"], ["Admin", "admin@college.edu"],
];

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault(); setErr(""); setBusy(true);
    try { const r = await api("/auth/login", { method: "POST", json: { email, password } }); login(r.token, r.user); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  }
  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <h1>Green Sheet Portal</h1>
        <p className="muted">Sign in with your official college or club email.</p>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <Alert>{err}</Alert>
        <button disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        <details className="demo">
          <summary>Demo accounts (password: password123)</summary>
          {DEMO.map(([l, em]) => <button type="button" key={em} className="link" onClick={() => { setEmail(em); setPassword("password123"); }}>{l} - {em}</button>)}
        </details>
      </form>
    </div>
  );
}
