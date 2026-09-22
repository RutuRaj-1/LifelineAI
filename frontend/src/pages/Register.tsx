import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, ROLE_HOME } from "../lib/auth";
import { ApiError, Role } from "../lib/api";
import Banner from "../components/Banner";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [role, setRole] = useState<Extract<Role, "patient" | "family">>("patient");
  const [form, setForm] = useState({ full_name: "", email: "", password: "", phone: "", dob: "", gender: "", blood_group: "", family_code: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof form>(k: K, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await register({ ...form, role });
      nav(ROLE_HOME[me.role]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12">
      <h1 className="mb-6 text-center font-display text-2xl font-semibold text-navy-900">Create an account</h1>
      <form onSubmit={submit} className="card space-y-4 p-6">
        {error && <Banner>{error}</Banner>}
        <div className="flex gap-2">
          {(["patient", "family"] as const).map((r) => (
            <button key={r} type="button" onClick={() => setRole(r)}
              className={`btn ${role === r ? "btn-primary" : "btn-secondary"} flex-1 capitalize`}>{r}</button>
          ))}
        </div>
        <div><label className="label">Full name</label><input className="input" required value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></div>
        <div><label className="label">Email</label><input className="input" type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} /></div>
        <div><label className="label">Password</label><input className="input" type="password" required minLength={8} value={form.password} onChange={(e) => set("password", e.target.value)} /></div>
        <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} /></div>
        {role === "patient" ? (
          <div className="grid grid-cols-3 gap-2">
            <div><label className="label">DOB</label><input className="input" type="date" value={form.dob} onChange={(e) => set("dob", e.target.value)} /></div>
            <div><label className="label">Gender</label><input className="input" value={form.gender} onChange={(e) => set("gender", e.target.value)} /></div>
            <div><label className="label">Blood grp</label><input className="input" value={form.blood_group} onChange={(e) => set("blood_group", e.target.value)} /></div>
          </div>
        ) : (
          <div><label className="label">Patient's family code</label>
            <input className="input" required placeholder="e.g. 4F2A1B" value={form.family_code} onChange={(e) => set("family_code", e.target.value.toUpperCase())} />
            <p className="mt-1 text-xs text-navy-900/50">Ask the patient for their family code, shown on their profile page.</p>
          </div>
        )}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        <p className="text-center text-sm text-navy-900/60">Already have an account? <Link to="/login" className="text-teal-600 hover:underline">Sign in</Link></p>
      </form>
    </div>
  );
}
