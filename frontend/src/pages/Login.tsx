import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, ROLE_HOME } from "../lib/auth";
import { ApiError } from "../lib/api";
import Banner from "../components/Banner";

const DEMO = [
  { label: "Patient", email: "patient1@lifeline.demo", password: "Patient@123" },
  { label: "Doctor", email: "doctor1@lifeline.demo", password: "Doctor@123" },
  { label: "Hospital", email: "hospital1@lifeline.demo", password: "Hospital@123" },
  { label: "Family", email: "family1@lifeline.demo", password: "Family@123" },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await login(email, password);
      nav(ROLE_HOME[me.role]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <div className="mb-8 text-center">
        <p className="text-2xl" aria-hidden>🫀</p>
        <h1 className="mt-2 font-display text-2xl font-semibold text-navy-900">LifeLine AI</h1>
        <p className="mt-1 text-sm text-navy-900/60">Patient-triggered emergency pre-arrival intelligence</p>
      </div>
      <form onSubmit={submit} className="card space-y-4 p-6">
        {error && <Banner>{error}</Banner>}
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="text-center text-sm text-navy-900/60">
          New patient or family member? <Link to="/register" className="text-teal-600 hover:underline">Create an account</Link>
        </p>
      </form>
      <div className="mt-6 card p-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-navy-900/50">Demo logins</p>
        <div className="grid grid-cols-2 gap-2">
          {DEMO.map((d) => (
            <button key={d.email} type="button" className="btn-secondary justify-start text-xs"
              onClick={() => { setEmail(d.email); setPassword(d.password); }}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
