import React, { createContext, useContext, useEffect, useState } from "react";
import { api, Me, Role } from "./api";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  register: (body: Record<string, unknown>) => Promise<Me>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!api.getToken()) {
      setLoading(false);
      return;
    }
    api.get<Me>("/auth/me").then(setMe).catch(() => api.setToken(null)).finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const res = await api.post<{ access_token: string; user: Me }>("/auth/login", { email, password });
    api.setToken(res.access_token);
    setMe(res.user);
    return res.user;
  }

  async function register(body: Record<string, unknown>) {
    const res = await api.post<{ access_token: string; user: Me }>("/auth/register", body);
    api.setToken(res.access_token);
    setMe(res.user);
    return res.user;
  }

  function logout() {
    api.setToken(null);
    setMe(null);
  }

  return <Ctx.Provider value={{ me, loading, login, register, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}

export const ROLE_HOME: Record<Role, string> = {
  patient: "/patient", doctor: "/doctor", hospital: "/hospital", family: "/family",
};
