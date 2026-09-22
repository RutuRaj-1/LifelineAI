import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAuth, ROLE_HOME } from "../lib/auth";

/* ─── tiny inline SVG icons ─────────────────────────────────────────── */
const icons = {
  heart: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
    </svg>
  ),
  bolt: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  ),
  brain: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
    </svg>
  ),
  shield: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  ),
  map: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  ),
  activity: (
    <svg viewBox="0 0 24 24" fill="none" className="w-6 h-6" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  ),
  chevron: (
    <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
  ),
  arrowDown: (
    <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
    </svg>
  ),
};

/* ─── Animated heartbeat line ─────────────────────────────────────────── */
function HeartbeatLine() {
  return (
    <svg
      viewBox="0 0 800 80"
      preserveAspectRatio="none"
      className="absolute inset-0 w-full h-full opacity-20"
      aria-hidden
    >
      <polyline
        points="0,40 100,40 130,10 160,70 190,5 220,75 250,40 800,40"
        fill="none"
        stroke="#0E8C82"
        strokeWidth="2"
        className="heartbeat-line"
      />
    </svg>
  );
}

/* ─── Feature card ─────────────────────────────────────────────────────── */
function FeatureCard({ icon, title, desc, gradient }: { icon: JSX.Element; title: string; desc: string; gradient: string }) {
  return (
    <div className={`group relative overflow-hidden rounded-2xl border border-white/10 p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl hover:shadow-teal-500/10 hover:border-teal-500/40`}>
      <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${gradient}`} />
      <div className="relative z-10">
        <div className="mb-4 inline-flex items-center justify-center rounded-xl bg-teal-500/10 p-3 text-teal-400 ring-1 ring-teal-500/20">
          {icon}
        </div>
        <h3 className="mb-2 font-display text-lg font-semibold text-white">{title}</h3>
        <p className="text-sm leading-relaxed text-slate-400">{desc}</p>
      </div>
    </div>
  );
}

/* ─── Pipeline step ────────────────────────────────────────────────────── */
function Step({ num, label, sub }: { num: number; label: string; sub: string }) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-500/10 ring-2 ring-teal-500/30 text-teal-400 font-bold text-lg mb-3">
        {num}
      </div>
      <p className="font-semibold text-white text-sm">{label}</p>
      <p className="mt-1 text-xs text-slate-500">{sub}</p>
    </div>
  );
}

/* ─── Stat card ─────────────────────────────────────────────────────────── */
function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="font-display text-4xl font-bold text-teal-400">{value}</p>
      <p className="mt-1 text-sm text-slate-400">{label}</p>
    </div>
  );
}

/* ─── Role card ─────────────────────────────────────────────────────────── */
function RoleCard({ emoji, role, items }: { emoji: string; role: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-5 hover:border-teal-500/40 transition-colors duration-300">
      <div className="mb-3 text-2xl">{emoji}</div>
      <h4 className="font-display font-semibold text-white mb-3">{role}</h4>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2 text-xs text-slate-400">
            <span className="mt-0.5 text-teal-500">✓</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ─── Animated counter ──────────────────────────────────────────────────── */
function useCounter(target: number, duration = 1500) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const obs = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      obs.disconnect();
      const start = Date.now();
      const tick = () => {
        const p = Math.min((Date.now() - start) / duration, 1);
        setVal(Math.round(p * target));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.5 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target, duration]);
  return { val, ref };
}

/* ─── Animated status ticker ─────────────────────────────────────────────── */
const STATUSES = [
  { label: "CREATED", color: "bg-slate-500" },
  { label: "PATIENT IDENTIFIED", color: "bg-blue-500" },
  { label: "SUMMARY GENERATED", color: "bg-purple-500" },
  { label: "DOCTOR ASSIGNED", color: "bg-amber-500" },
  { label: "ROOM RESERVED", color: "bg-teal-500" },
  { label: "PATIENT ARRIVED", color: "bg-green-500" },
];

function StatusTicker() {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setActive((p) => (p + 1) % STATUSES.length), 1800);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-sm">
      <p className="mb-3 text-xs font-medium uppercase tracking-widest text-slate-500">Live Pipeline</p>
      <div className="space-y-2">
        {STATUSES.map((s, i) => (
          <div key={s.label} className={`flex items-center gap-2 transition-all duration-500 ${i === active ? "opacity-100" : "opacity-30"}`}>
            <span className={`h-2 w-2 rounded-full flex-shrink-0 ${s.color} ${i === active ? "animate-pulse" : ""}`} />
            <span className="text-xs text-slate-300">{s.label}</span>
            {i === active && <span className="ml-auto text-xs text-teal-400">→ Now</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Main Component ─────────────────────────────────────────────────────── */
export default function LandingPage() {
  const { me } = useAuth();
  const { val: h, ref: hRef } = useCounter(3);
  const { val: d, ref: dRef } = useCounter(8);
  const { val: p, ref: pRef } = useCounter(10);
  const { val: r, ref: rRef } = useCounter(50);

  return (
    <div className="min-h-screen bg-[#060E1A] text-white">
      {/* ── Navbar ──────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-[#060E1A]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🫀</span>
            <span className="font-display text-xl font-bold tracking-tight">LifeLine <span className="text-teal-400">AI</span></span>
          </div>
          <nav className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
            <a href="#features" className="hover:text-teal-400 transition-colors">Features</a>
            <a href="#how" className="hover:text-teal-400 transition-colors">How It Works</a>
            <a href="#roles" className="hover:text-teal-400 transition-colors">For Whom</a>
            <a href="#safety" className="hover:text-teal-400 transition-colors">Safety</a>
          </nav>
          <div className="flex items-center gap-3">
            {me ? (
              <Link to={ROLE_HOME[me.role]} className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-500 transition-colors shadow-lg shadow-teal-900/50">
                Dashboard ({me.role}) →
              </Link>
            ) : (
              <>
                <Link to="/login" className="rounded-lg border border-white/20 px-4 py-2 text-sm text-slate-300 hover:border-teal-500/50 hover:text-white transition-all duration-200">
                  Sign In
                </Link>
                <Link to="/register" className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-500 transition-colors shadow-lg shadow-teal-900/50">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden px-6 pt-24 pb-20 md:pt-32 md:pb-28">
        {/* Heartbeat animated background */}
        <HeartbeatLine />

        {/* Background grid */}
        <div className="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0wIDBoNDB2NDBIMHoiLz48cGF0aCBkPSJNMCAwaDFoMzl2MUgwek0wIDM5aDQwdjFIMHoiIHN0cm9rZT0icmdiYSgxNCwxNDAsMTMwLDAuMDcpIiBzdHJva2Utd2lkdGg9IjEiLz48cGF0aCBkPSJNMCAwdjFoMXYzOGgxVjBINDB2MUgxTTM5IDBoMXY0MEgzOXoiIHN0cm9rZT0icmdiYSgxNCwxNDAsMTMwLDAuMDcpIiBzdHJva2Utd2lkdGg9IjEiLz48L2c+PC9zdmc+')] opacity-40" />
        {/* Radial glow */}
        <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 h-[600px] w-[800px] rounded-full bg-teal-600/10 blur-3xl" />

        <div className="relative mx-auto max-w-7xl">
          <div className="mx-auto max-w-3xl text-center">
            {/* Badge */}
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1.5 text-xs font-medium text-teal-400">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" />
              AI-Powered Emergency Response — Works 100% Offline
            </div>

            <h1 className="font-display text-5xl font-bold leading-tight tracking-tight text-white md:text-7xl">
              Move <span className="bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">information</span>
              <br />before the patient
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-slate-400 md:text-xl">
              LifeLine AI prepares the hospital before the patient arrives — even without an ambulance.
              One tap SOS → AI medical brief → hospital routing → doctor assignment — in real time.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              {me ? (
                <Link
                  to={ROLE_HOME[me.role]}
                  className="group flex items-center gap-2 rounded-xl bg-teal-600 px-8 py-3.5 text-base font-semibold text-white shadow-xl shadow-teal-900/40 hover:bg-teal-500 transition-all duration-200 hover:shadow-teal-700/50"
                >
                  Go to Dashboard ({me.role})
                  <span className="group-hover:translate-x-0.5 transition-transform">{icons.chevron}</span>
                </Link>
              ) : (
                <Link
                  to="/login"
                  className="group flex items-center gap-2 rounded-xl bg-teal-600 px-8 py-3.5 text-base font-semibold text-white shadow-xl shadow-teal-900/40 hover:bg-teal-500 transition-all duration-200 hover:shadow-teal-700/50"
                >
                  Launch Demo
                  <span className="group-hover:translate-x-0.5 transition-transform">{icons.chevron}</span>
                </Link>
              )}
              <a
                href="#how"
                className="flex items-center gap-2 rounded-xl border border-white/15 px-8 py-3.5 text-base font-medium text-slate-300 hover:border-white/30 hover:text-white transition-all duration-200"
              >
                See How It Works
                {icons.arrowDown}
              </a>
            </div>
          </div>

          {/* Hero visuals */}
          <div className="mt-16 grid gap-4 md:grid-cols-3 max-w-4xl mx-auto">
            {/* Status ticker */}
            <div className="md:col-span-1">
              <StatusTicker />
            </div>
            {/* ETA mock */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-sm">
              <p className="text-xs font-medium uppercase tracking-widest text-slate-500 mb-3">ETA to Hospital</p>
              <p className="font-display text-4xl font-bold text-teal-400">8 <span className="text-lg text-slate-400">min</span></p>
              <div className="mt-3 h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-teal-600 to-cyan-400 animate-pulse" />
              </div>
              <p className="mt-2 text-xs text-slate-500">CityCare Multispecialty → FC Road, Pune</p>
            </div>
            {/* AI brief mock */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-sm">
              <p className="text-xs font-medium uppercase tracking-widest text-slate-500 mb-3">AI Medical Brief</p>
              <div className="space-y-2">
                <div className="flex justify-between text-xs"><span className="text-slate-400">Allergies</span><span className="text-coral-400 font-medium text-red-400">Penicillin ⚠</span></div>
                <div className="flex justify-between text-xs"><span className="text-slate-400">Conditions</span><span className="text-white">Hypertension, AF</span></div>
                <div className="flex justify-between text-xs"><span className="text-slate-400">Risk</span><span className="text-amber-400">Anticoagulant</span></div>
                <div className="flex justify-between text-xs"><span className="text-slate-400">Specialty</span><span className="text-teal-400">Neurology</span></div>
              </div>
              <p className="mt-3 text-[10px] italic text-slate-600">Summarizes records, never diagnoses</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Stats ─────────────────────────────────────────────────────────── */}
      <section className="border-y border-white/5 bg-white/[0.02] py-14">
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            <div ref={hRef}><Stat value={`${h}`} label="Hospitals Seeded" /></div>
            <div ref={dRef}><Stat value={`${d}`} label="Doctors Available" /></div>
            <div ref={pRef}><Stat value={`${p}`} label="Patients Registered" /></div>
            <div ref={rRef}><Stat value={`${r}+`} label="Medical Reports Indexed" /></div>
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-teal-500">Features</p>
            <h2 className="font-display text-4xl font-bold text-white">Everything the hospital needs<br/>before you even arrive</h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <FeatureCard
              icon={icons.bolt}
              title="One-Tap SOS"
              desc="Patients trigger an emergency with a single tap. GPS coordinates, emergency type, and symptoms are captured instantly."
              gradient="bg-gradient-to-br from-teal-600/5 to-transparent"
            />
            <FeatureCard
              icon={icons.brain}
              title="AI Medical Brief (RAG)"
              desc="OCR scans uploaded reports, FAISS indexes them, and LangGraph agents extract a cited medical summary — diseases, meds, allergies, risks."
              gradient="bg-gradient-to-br from-purple-600/5 to-transparent"
            />
            <FeatureCard
              icon={icons.map}
              title="Intelligent Hospital Routing"
              desc="Haversine + capability matching picks the nearest hospital with the right specialty and available resources for the emergency type."
              gradient="bg-gradient-to-br from-blue-600/5 to-transparent"
            />
            <FeatureCard
              icon={icons.shield}
              title="Doctor Assignment"
              desc="The agent auto-assigns an available specialist from the matched hospital. Doctors see the AI brief and checklist before the patient arrives."
              gradient="bg-gradient-to-br from-green-600/5 to-transparent"
            />
            <FeatureCard
              icon={icons.activity}
              title="Real-Time WebSocket Updates"
              desc="Every status change — CREATED → SUMMARY GENERATED → ROOM RESERVED — broadcasts live over WebSocket. No refresh needed."
              gradient="bg-gradient-to-br from-amber-600/5 to-transparent"
            />
            <FeatureCard
              icon={icons.users}
              title="Family Portal"
              desc="Family members get live status, ETA, and hospital name — but never symptoms or the AI brief. Clinical detail is staff-only by design."
              gradient="bg-gradient-to-br from-rose-600/5 to-transparent"
            />
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <section id="how" className="py-24 px-6 bg-white/[0.02] border-y border-white/5">
        <div className="mx-auto max-w-5xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-teal-500">Pipeline</p>
            <h2 className="font-display text-4xl font-bold text-white">From SOS to Ready Room<br/>in minutes</h2>
          </div>
          <div className="relative">
            {/* connector line */}
            <div className="absolute top-6 left-0 right-0 hidden h-0.5 bg-gradient-to-r from-transparent via-teal-500/30 to-transparent md:block" />
            <div className="grid gap-10 text-center md:grid-cols-6">
              <Step num={1} label="Patient Taps SOS" sub="GPS + emergency type captured" />
              <Step num={2} label="Patient Identified" sub="Profile pulled from DB" />
              <Step num={3} label="OCR + RAG" sub="Reports scanned & indexed" />
              <Step num={4} label="AI Brief" sub="Evidence-cited summary" />
              <Step num={5} label="Hospital Routing" sub="Nearest capable facility" />
              <Step num={6} label="Doctor + Room" sub="Assigned & reserved" />
            </div>
          </div>

          {/* Tech stack badges */}
          <div className="mt-16 flex flex-wrap justify-center gap-3">
            {["FastAPI", "SQLAlchemy", "LangGraph", "FAISS", "Tesseract OCR", "WebSocket", "React", "TypeScript", "SQLite / PostgreSQL"].map((t) => (
              <span key={t} className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-slate-400">
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Roles ─────────────────────────────────────────────────────────── */}
      <section id="roles" className="py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-teal-500">Dashboards</p>
            <h2 className="font-display text-4xl font-bold text-white">Built for every stakeholder<br/>in the emergency chain</h2>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <RoleCard
              emoji="🧑‍⚕️"
              role="Patient"
              items={["Medical profile & report upload", "One-tap SOS with GPS", "Live ETA & status tracking", "AI brief consent management"]}
            />
            <RoleCard
              emoji="🏥"
              role="Hospital"
              items={["Priority-sorted emergency queue", "Live resource counts (ER/ICU/OT)", "Doctor assignment & room prep", "Demo pipeline triggers (5 scenarios)"]}
            />
            <RoleCard
              emoji="👨‍⚕️"
              role="Doctor"
              items={["Assigned case view", "AI medical summary with citations", "Uploaded reports & OCR output", "Preparation checklist"]}
            />
            <RoleCard
              emoji="👨‍👩‍👧"
              role="Family"
              items={["Live status & ETA", "Hospital name & contact", "No symptoms shown (by design)", "Privacy-first notifications"]}
            />
          </div>
        </div>
      </section>

      {/* ── Safety guarantees ─────────────────────────────────────────────── */}
      <section id="safety" className="py-24 px-6 border-t border-white/5 bg-white/[0.02]">
        <div className="mx-auto max-w-4xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-teal-500">Safety</p>
            <h2 className="font-display text-4xl font-bold text-white">Non-negotiable rules,<br/>enforced in code</h2>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            {[
              { num: "01", title: "AI Never Diagnoses", desc: "Every item in the brief has a citation to an uploaded report. The AI restates facts — it never infers a diagnosis." },
              { num: "02", title: "Doctor in the Loop", desc: "AI output is decision support only. Every clinical action — assignment, preparation, arrival — requires a doctor's sign-off." },
              { num: "03", title: "Family Privacy", desc: "Family members see status, ETA, and hospital. Symptoms and the AI medical brief are strictly staff-only." },
            ].map((g) => (
              <div key={g.num} className="rounded-2xl border border-teal-500/20 bg-teal-500/5 p-6">
                <p className="font-display text-4xl font-bold text-teal-500/30 mb-3">{g.num}</p>
                <h3 className="font-semibold text-white mb-2">{g.title}</h3>
                <p className="text-sm text-slate-400">{g.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────────── */}
      <section className="py-24 px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="relative rounded-3xl border border-teal-500/20 bg-gradient-to-br from-teal-900/30 to-[#060E1A] p-12 overflow-hidden">
            <div className="pointer-events-none absolute inset-0 rounded-3xl bg-teal-500/5" />
            <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-48 w-64 rounded-full bg-teal-600/20 blur-3xl" />
            <div className="relative">
              <p className="text-4xl mb-4">🫀</p>
              <h2 className="font-display text-3xl font-bold text-white mb-4">Ready to try it?</h2>
              <p className="text-slate-400 mb-8 text-base">Use the demo logins — no setup required. Every feature works offline with seeded data.</p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link to="/login" className="w-full sm:w-auto rounded-xl bg-teal-600 px-8 py-3.5 text-base font-semibold text-white hover:bg-teal-500 transition-colors shadow-xl shadow-teal-900/50">
                  Open App → Sign In
                </Link>
                <Link to="/register" className="w-full sm:w-auto rounded-xl border border-white/15 px-8 py-3.5 text-base font-medium text-slate-300 hover:border-white/30 hover:text-white transition-colors">
                  Create Patient Account
                </Link>
              </div>

              {/* Demo credentials quick reference */}
              <div className="mt-8 grid grid-cols-2 gap-2 text-left sm:grid-cols-4">
                {[
                  { role: "Patient", email: "patient1@lifeline.demo", pw: "Patient@123" },
                  { role: "Doctor", email: "doctor1@lifeline.demo", pw: "Doctor@123" },
                  { role: "Hospital", email: "hospital1@lifeline.demo", pw: "Hospital@123" },
                  { role: "Family", email: "family1@lifeline.demo", pw: "Family@123" },
                ].map((d) => (
                  <div key={d.role} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs">
                    <p className="font-semibold text-teal-400 mb-1">{d.role}</p>
                    <p className="text-slate-500 break-all">{d.email}</p>
                    <p className="text-slate-400 font-mono mt-0.5">{d.pw}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-10 px-6 text-center text-sm text-slate-600">
        <div className="flex items-center justify-center gap-2 mb-3">
          <span className="text-base">🫀</span>
          <span className="font-display font-semibold text-slate-400">LifeLine AI</span>
        </div>
        <p>Patient-Triggered Emergency Pre-Arrival Intelligence · Built at VIT EDI 5 Conference</p>
        <p className="mt-1">AI never diagnoses — it only restates facts from uploaded records, with citations.</p>
      </footer>
    </div>
  );
}
