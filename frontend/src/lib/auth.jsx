import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const Ctx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("nv_token");
    if (!t) { setLoading(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => {
      localStorage.removeItem("nv_token");
    }).finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("nv_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };

  const signup = async (email, password, name) => {
    const r = await api.post("/auth/signup", { email, password, name });
    localStorage.setItem("nv_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    localStorage.removeItem("nv_token");
    setUser(null);
  };

  const refresh = async () => {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
    } catch (_) { /* ignore */ }
  };

  return <Ctx.Provider value={{ user, loading, login, signup, logout, refresh }}>{children}</Ctx.Provider>;
};

export const useAuth = () => useContext(Ctx);
