import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { KeyRound, Save, Info } from "lucide-react";
import { toast } from "sonner";

// providers with multiple fields
const PROVIDERS = [
  { k: "openai", label: "OpenAI", desc: "gpt-5.x · vision · embeddings", fields: [
    { k: "api_key", label: "API KEY", ph: "sk-…" },
  ]},
  { k: "anthropic", label: "Anthropic", desc: "Claude Sonnet 4.x", fields: [
    { k: "api_key", label: "API KEY", ph: "sk-ant-…" },
  ]},
  { k: "gemini", label: "Google Gemini", desc: "gemini-flash-latest · powers vision detections", fields: [
    { k: "api_key", label: "API KEY", ph: "AIza… or AQ.…" },
  ]},
  { k: "twilio", label: "Twilio", desc: "WhatsApp · SMS · Voice", fields: [
    { k: "sid", label: "ACCOUNT SID", ph: "ACxxxxxxxxxxxxxxxxxxxxxxxxxx" },
    { k: "token", label: "AUTH TOKEN" },
    { k: "from", label: "FROM NUMBER", ph: "whatsapp:+14155238886  or  +15551234567" },
  ]},
  { k: "plivo", label: "Plivo", desc: "SMS · WhatsApp · India-friendly", fields: [
    { k: "auth_id", label: "AUTH ID" },
    { k: "auth_token", label: "AUTH TOKEN" },
    { k: "from", label: "FROM NUMBER" },
  ]},
  { k: "exotel", label: "Exotel", desc: "SMS · Voice · India", fields: [
    { k: "api_key", label: "API KEY" },
    { k: "api_token", label: "API TOKEN" },
    { k: "account_sid", label: "ACCOUNT SID" },
    { k: "from", label: "FROM (EXOPHONE)" },
  ]},
  { k: "vonage", label: "Vonage / Nexmo", desc: "SMS · Global", fields: [
    { k: "api_key", label: "API KEY" },
    { k: "api_secret", label: "API SECRET" },
    { k: "from", label: "SENDER ID / FROM" },
  ]},
  { k: "messagebird", label: "MessageBird", desc: "SMS · Global", fields: [
    { k: "api_key", label: "ACCESS KEY" },
    { k: "from", label: "ORIGINATOR" },
  ]},
];

export default function Settings() {
  const [current, setCurrent] = useState({});
  const [drafts, setDrafts] = useState({});   // { provider: { field: value } }
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState({});

  useEffect(() => {
    api.get("/settings/byo").then((r)=>setCurrent(r.data.keys || {}));
  }, []);

  const set = (prov, field, value) => setDrafts((d) => ({ ...d, [prov]: { ...(d[prov] || {}), [field]: value } }));

  const save = async () => {
    setBusy(true);
    try {
      // filter empty
      const payload = {};
      Object.entries(drafts).forEach(([prov, fields]) => {
        const clean = {};
        Object.entries(fields || {}).forEach(([fk, fv]) => { if (fv) clean[fk] = fv; });
        if (Object.keys(clean).length > 0) payload[prov] = clean;
      });
      if (Object.keys(payload).length === 0) { toast("Nothing to save"); return; }
      await api.post("/settings/byo", payload);
      toast.success("Keys saved (masked at rest)");
      const r = await api.get("/settings/byo");
      setCurrent(r.data.keys || {});
      setDrafts({});
    } catch (e) { toast.error("Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="p-8 max-w-[900px]">
      <div className="mb-6">
        <h1 className="font-display font-black text-4xl tracking-tighter">Settings</h1>
        <p className="text-[13px] text-[#a3a3a3] mt-1">Bring your own model & telephony keys. NVision fees drop to orchestration only.</p>
      </div>

      <div className="nv-card mb-6">
        <div className="px-5 py-3 border-b border-[#262626] font-display font-bold flex items-center gap-2"><KeyRound size={14}/> BYO Provider Keys</div>
        <div className="divide-y divide-[#262626]">
          {PROVIDERS.map((p) => {
            const saved = current[p.k];
            const savedCount = saved && typeof saved === "object" ? Object.values(saved).filter(Boolean).length : (typeof saved === "string" && saved ? 1 : 0);
            const isOpen = !!open[p.k] || savedCount === 0;
            return (
              <div key={p.k} className="p-4">
                <button type="button" onClick={()=>setOpen({...open, [p.k]: !isOpen})}
                  className="w-full flex items-center justify-between gap-4"
                  data-testid={`byo-${p.k}-toggle`}
                >
                  <div className="text-left">
                    <div className="font-display font-bold flex items-center gap-2">
                      {p.label}
                      {savedCount > 0 && <span className="text-[10px] font-mono tracking-widest text-[#ccff00] border border-[#ccff00]/40 px-1.5 py-0.5">CONFIGURED · {savedCount}</span>}
                    </div>
                    <div className="text-[11px] text-[#737373] font-mono">{p.desc}</div>
                  </div>
                  <div className="text-[#a3a3a3]">{isOpen ? "−" : "+"}</div>
                </button>
                {isOpen && (
                  <div className="mt-3 space-y-2">
                    {p.fields.map((f) => (
                      <label key={f.k} className="block">
                        <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">{f.label}</span>
                        <input
                          type={f.k.includes("token") || f.k.includes("secret") || f.k.includes("api_key") ? "password" : "text"}
                          value={drafts[p.k]?.[f.k] || ""}
                          onChange={(e)=>set(p.k, f.k, e.target.value)}
                          placeholder={saved && saved[f.k] ? `Saved: ${saved[f.k]}` : (f.ph || "")}
                          className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none"
                          data-testid={`byo-${p.k}-${f.k}`}
                        />
                      </label>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="p-4 border-t border-[#262626] flex justify-end">
          <button onClick={save} disabled={busy || Object.keys(drafts).length === 0} className="nv-hard-btn text-sm inline-flex items-center gap-2" data-testid="save-keys">
            <Save size={13}/> {busy ? "…" : "Save keys"}
          </button>
        </div>
      </div>

      <div className="nv-card p-5 mb-6">
        <div className="font-display font-bold mb-2 flex items-center gap-2"><Info size={14} className="text-[#ccff00]"/> Twilio WhatsApp — Quick setup</div>
        <ol className="text-[13px] text-[#a3a3a3] space-y-1.5 list-decimal pl-5">
          <li>Sign up at <span className="font-mono text-[#ccff00]">twilio.com</span> (free trial).</li>
          <li>Get <span className="font-mono">Account SID</span> and <span className="font-mono">Auth Token</span> from Console dashboard.</li>
          <li>For WhatsApp sandbox: Messaging → Try it out → Send a WhatsApp message. Send &quot;join &lt;code&gt;&quot; from your phone to <span className="font-mono text-[#ccff00]">+1 415 523 8886</span>. From-number is <span className="font-mono">whatsapp:+14155238886</span>.</li>
          <li>Paste all three above → save → in Alerts, add a WhatsApp channel with provider=twilio → send test.</li>
        </ol>
      </div>

      <div className="nv-card p-5">
        <div className="font-display font-bold mb-2">Privacy</div>
        <ul className="text-[13px] text-[#a3a3a3] space-y-1 list-disc pl-5">
          <li>Face recognition is <span className="text-[#ccff00]">off</span> by default (v1 policy).</li>
          <li>Events logged at object level (&quot;a person&quot;), never identity level.</li>
          <li>Privacy-mask zones can be defined per camera (see Cameras page).</li>
          <li>Data deletion on request. GST-compliant invoices for India via Razorpay.</li>
        </ul>
      </div>
    </div>
  );
}
