import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { KeyRound, Save } from "lucide-react";
import { toast } from "sonner";

const PROVIDERS = [
  { k: "openai", label: "OpenAI", desc: "gpt-5.x, vision, embeddings" },
  { k: "anthropic", label: "Anthropic", desc: "Claude Sonnet 4.x" },
  { k: "gemini", label: "Google Gemini", desc: "gemini-3-flash-preview" },
  { k: "twilio", label: "Twilio", desc: "WhatsApp / SMS / Voice" },
  { k: "plivo", label: "Plivo", desc: "SMS / Voice · India" },
  { k: "exotel", label: "Exotel", desc: "Voice · India" },
];

export default function Settings() {
  const [current, setCurrent] = useState({});
  const [keys, setKeys] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/settings/byo").then((r)=>setCurrent(r.data.keys || {}));
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      const payload = {};
      Object.entries(keys).forEach(([k,v])=>{ if (v) payload[k] = v; });
      await api.post("/settings/byo", payload);
      toast.success("Keys saved (encrypted at rest)");
      const r = await api.get("/settings/byo");
      setCurrent(r.data.keys || {});
      setKeys({});
    } catch (e) { toast.error("Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="p-8 max-w-[900px]">
      <div className="mb-6">
        <h1 className="font-display font-black text-4xl tracking-tighter">Settings</h1>
        <p className="text-[13px] text-[#a3a3a3] mt-1">Bring your own model & telephony keys. NVision fees drop to orchestration only.</p>
      </div>

      <div className="nv-card">
        <div className="px-5 py-3 border-b border-[#262626] font-display font-bold flex items-center gap-2"><KeyRound size={14}/> BYO Provider Keys</div>
        <div className="divide-y divide-[#262626]">
          {PROVIDERS.map((p) => (
            <div key={p.k} className="p-4 grid md:grid-cols-[200px_1fr] gap-4 items-center">
              <div>
                <div className="font-display font-bold">{p.label}</div>
                <div className="text-[11px] text-[#737373] font-mono">{p.desc}</div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="password"
                  value={keys[p.k] || ""}
                  onChange={(e)=>setKeys({...keys, [p.k]: e.target.value})}
                  placeholder={current[p.k] ? `Saved: ${current[p.k]}` : "sk-… / auth-token"}
                  className="flex-1 bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none"
                  data-testid={`key-${p.k}`}
                />
                {current[p.k] && <span className="text-[10px] font-mono text-[#ccff00] tracking-widest">SAVED</span>}
              </div>
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-[#262626] flex justify-end">
          <button onClick={save} disabled={busy || Object.keys(keys).length === 0} className="nv-hard-btn text-sm inline-flex items-center gap-2" data-testid="save-keys">
            <Save size={13}/> {busy ? "…" : "Save keys"}
          </button>
        </div>
      </div>

      <div className="mt-6 nv-card p-5">
        <div className="font-display font-bold mb-2">Privacy</div>
        <ul className="text-[13px] text-[#a3a3a3] space-y-1 list-disc pl-5">
          <li>Face recognition is <span className="text-[#ccff00]">off</span> by default (v1 policy).</li>
          <li>Events are logged at object level (&quot;a person&quot;), never identity level.</li>
          <li>Privacy-mask zones can be defined per camera (Phase 2 editor).</li>
          <li>Data deletion on request. GST-compliant invoices for India.</li>
        </ul>
      </div>
    </div>
  );
}
