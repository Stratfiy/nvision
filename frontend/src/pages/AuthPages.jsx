import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Eye } from "lucide-react";
import { toast } from "sonner";

function Field({ label, testid, ...props }) {
  return (
    <label className="block mb-4">
      <span className="block text-[11px] tracking-widest text-[#a3a3a3] font-mono mb-1.5">{label}</span>
      <input
        data-testid={testid}
        className="w-full bg-[#050505] border border-[#262626] px-3 py-2.5 text-[14px] focus:border-[#ccff00] outline-none font-mono"
        {...props}
      />
    </label>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, pw);
      toast.success("Welcome back");
      nav("/app");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="nv-grain min-h-screen grid place-items-center px-6">
      <div className="w-full max-w-sm relative">
        <Link to="/" className="flex items-center gap-2 mb-10">
          <div className="w-6 h-6 bg-[#ccff00] grid place-items-center"><Eye size={13} className="text-black" strokeWidth={2.5}/></div>
          <span className="font-display font-black tracking-tight">NVISION</span>
        </Link>
        <h1 className="font-display text-3xl font-black tracking-tight mb-2">Log in.</h1>
        <p className="text-[13px] text-[#a3a3a3] mb-8">Continue watching what matters.</p>
        <form onSubmit={submit}>
          <Field label="EMAIL" type="email" required value={email} onChange={(e)=>setEmail(e.target.value)} testid="login-email" />
          <Field label="PASSWORD" type="password" required value={pw} onChange={(e)=>setPw(e.target.value)} testid="login-password" />
          <button data-testid="login-submit" disabled={busy} className="nv-hard-btn w-full mt-2 text-sm">{busy ? "…" : "Log in →"}</button>
        </form>
        <div className="mt-6 text-[12px] text-[#737373]">
          No account? <Link to="/signup" data-testid="login-to-signup" className="text-[#ccff00] hover:underline">Get 500 free credits →</Link>
        </div>
      </div>
    </div>
  );
}

export function SignupPage() {
  const { signup } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signup(email, pw, name);
      toast.success("Welcome to NVision. 500 credits added.");
      nav("/app");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Signup failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="nv-grain min-h-screen grid place-items-center px-6">
      <div className="w-full max-w-sm relative">
        <Link to="/" className="flex items-center gap-2 mb-10">
          <div className="w-6 h-6 bg-[#ccff00] grid place-items-center"><Eye size={13} className="text-black" strokeWidth={2.5}/></div>
          <span className="font-display font-black tracking-tight">NVISION</span>
        </Link>
        <h1 className="font-display text-3xl font-black tracking-tight mb-2">Start free.</h1>
        <p className="text-[13px] text-[#a3a3a3] mb-8">500 credits on us. No card required.</p>
        <form onSubmit={submit}>
          <Field label="NAME" required value={name} onChange={(e)=>setName(e.target.value)} testid="signup-name" />
          <Field label="EMAIL" type="email" required value={email} onChange={(e)=>setEmail(e.target.value)} testid="signup-email" />
          <Field label="PASSWORD (min 6)" type="password" required minLength={6} value={pw} onChange={(e)=>setPw(e.target.value)} testid="signup-password" />
          <button data-testid="signup-submit" disabled={busy} className="nv-hard-btn w-full mt-2 text-sm">{busy ? "…" : "Create account →"}</button>
        </form>
        <div className="mt-6 text-[12px] text-[#737373]">
          Already have one? <Link to="/login" data-testid="signup-to-login" className="text-[#ccff00] hover:underline">Log in →</Link>
        </div>
      </div>
    </div>
  );
}
