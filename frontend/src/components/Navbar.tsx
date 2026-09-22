import { NavLink, useLocation } from "react-router-dom";
import { useAuth, ROLE_HOME } from "../lib/auth";

export default function Navbar() {
  const { me, logout } = useAuth();
  const location = useLocation();
  if (!me || location.pathname === "/") return null;
  return (
    <header className="sticky top-0 z-20 border-b border-navy-900/10 bg-navy-700 text-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="text-lg" aria-hidden>🫀</span>
          <span className="font-display text-lg font-semibold tracking-tight">LifeLine AI</span>
          <span className="ml-2 hidden pill bg-white/10 text-white/70 sm:inline-flex">{me.role}</span>
        </div>
        <nav className="flex items-center gap-4 text-sm">
          <NavLink to={ROLE_HOME[me.role]} end className={({ isActive }) => `hover:text-teal-200 ${isActive ? "text-teal-200" : "text-white/80"}`}>
            Dashboard
          </NavLink>
          <NavLink to="/" end className={({ isActive }) => `hover:text-teal-200 ${isActive ? "text-teal-200" : "text-white/80"}`}>
            About
          </NavLink>
          <span className="hidden text-white/50 sm:inline">{me.full_name}</span>
          <button onClick={logout} className="btn-secondary !bg-transparent !text-white !border-white/25 hover:!bg-white/10">
            Log out
          </button>
        </nav>
      </div>
    </header>
  );
}
