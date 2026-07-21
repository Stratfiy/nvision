import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Plus, X, Bell, Trash2, Send, MessageCircle, Slack, Webhook, Mail, Phone, PhoneCall, Users } from "lucide-react";
import { toast } from "sonner";

const KINDS = [
  { key: "slack",    label: "Slack",         icon: Slack,        desc: "Fully functional. Paste incoming webhook URL." },
  { key: "webhook",  label: "Webhook",       icon: Webhook,      desc: "Fully functional. HMAC signed POST to your URL." },
  { key: "whatsapp", label: "WhatsApp",      icon: MessageCircle, desc: "Simulated for MVP. Add Twilio/Plivo keys in Settings — Phase 2." },
  { key: "email",    label: "Email",         icon: Mail,          desc: "Simulated for MVP. Delivery logged." },
  { key: "sms",      label: "SMS",           icon: Phone,         desc: "Simulated for MVP. DLT-ready templates." },
  { key: "voice",    label: "Voice call",    icon: PhoneCall,     desc: "Simulated for MVP. TTS reads alert." },
  { key: "teams",    label: "Microsoft Teams", icon: Users,       desc: "Simulated for MVP." },
];

export default function Alerts() {
  const [chs, setChs] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [deliveries, setDeliveries] = useState([]);

  const load = () => {
    api.get("/channels").then((r) => setChs(r.data));
    api.get("/deliveries").then((r) => setDeliveries(r.data));
  };
  useEffect(() => { load(); }, []);

  const del = async (id) => {
    if (!window.confirm("Delete channel?")) return;
    await api.delete(`/channels/${id}`);
    load();
  };

  const test = async (id) => {
    try {
      const r = await api.post("/channels/test", { channel_id: id, message: "NVision test alert — this is a drill." });
      toast.success(`Test: ${r.data.status}`);
      load();
    } catch (e) { toast.error("Failed"); }
  };

  const toggle = async (ch) => {
    await api.patch(`/channels/${ch.id}`, { enabled: !ch.enabled });
    load();
  };

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="font-display font-black text-4xl tracking-tighter">Alerts</h1>
          <p className="text-[13px] text-[#a3a3a3] mt-1">Channels fan out on every match. Slack & Webhook are live — others simulate in MVP.</p>
        </div>
        <button onClick={()=>setShowAdd(true)} className="nv-hard-btn inline-flex items-center gap-2 text-sm" data-testid="add-channel-btn">
          <Plus size={14}/> Add channel
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-3 mb-8">
        {chs.length === 0 && (
          <div className="nv-card p-10 text-center col-span-full">
            <Bell size={36} className="mx-auto text-[#525252] mb-3" strokeWidth={1.2}/>
            <div className="font-display font-bold text-lg mb-1">No channels yet.</div>
            <div className="text-[13px] text-[#a3a3a3]">Wire up Slack, Webhook, WhatsApp or a phone call.</div>
          </div>
        )}
        {chs.map((c) => {
          const K = KINDS.find((k) => k.key === c.kind) || KINDS[0];
          return (
            <div key={c.id} className="nv-card p-4" data-testid={`channel-${c.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 grid place-items-center bg-[#1e1e1e] border border-[#262626]">
                    <K.icon size={16} className="text-[#ccff00]" strokeWidth={1.5}/>
                  </div>
                  <div>
                    <div className="font-display font-bold">{c.name}</div>
                    <div className="text-[11px] font-mono text-[#737373]">{c.kind.toUpperCase()}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={()=>toggle(c)} className={`text-[10px] font-mono tracking-widest px-2 py-1 border ${c.enabled ? "border-[#ccff00] text-[#ccff00]" : "border-[#262626] text-[#737373]"}`} data-testid={`toggle-${c.id}`}>
                    {c.enabled ? "ON" : "OFF"}
                  </button>
                  <button onClick={()=>test(c.id)} className="text-[#a3a3a3] hover:text-[#ccff00] p-1" title="Send test" data-testid={`test-${c.id}`}><Send size={14}/></button>
                  <button onClick={()=>del(c.id)} className="text-[#a3a3a3] hover:text-[#ff3366] p-1" data-testid={`del-ch-${c.id}`}><Trash2 size={14}/></button>
                </div>
              </div>
              <div className="mt-3 text-[11px] font-mono text-[#a3a3a3] truncate">
                {Object.entries(c.config).map(([k,v])=>`${k}=${String(v).slice(0,40)}`).join(" · ")}
              </div>
            </div>
          );
        })}
      </div>

      {/* Deliveries log */}
      <div className="nv-card">
        <div className="px-5 py-3 border-b border-[#262626] font-display font-bold flex items-center gap-2"><Bell size={14}/> Delivery log</div>
        {deliveries.length === 0 ? (
          <div className="p-8 text-center text-[13px] text-[#737373]">Nothing delivered yet.</div>
        ) : (
          <table className="w-full text-[12px]">
            <thead className="text-[10px] tracking-widest text-[#737373] font-mono">
              <tr className="border-b border-[#262626]"><th className="text-left px-5 py-2">TIME</th><th className="text-left">KIND</th><th className="text-left">SUBJECT</th><th className="text-left px-5">STATUS</th></tr>
            </thead>
            <tbody className="font-mono">
              {deliveries.map((d)=>(
                <tr key={d.id} className="border-b border-[#262626] last:border-none">
                  <td className="px-5 py-2 text-[#a3a3a3]">{d.ts?.slice(0,19).replace("T"," ")}</td>
                  <td className="text-[#ccff00]">{d.kind}</td>
                  <td className="text-[#e5e5e5] truncate max-w-[300px]">{d.subject}</td>
                  <td className={`px-5 ${d.status==="sent"?"text-[#ccff00]":d.status==="simulated"?"text-[#ffb800]":"text-[#ff3366]"}`}>{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAdd && <AddChannel onClose={()=>{ setShowAdd(false); load(); }} />}
    </div>
  );
}

function AddChannel({ onClose }) {
  const [kind, setKind] = useState("slack");
  const [name, setName] = useState("");
  const [config, setConfig] = useState({});
  const [busy, setBusy] = useState(false);

  const K = KINDS.find((k) => k.key === kind);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/channels", { name, kind, config });
      toast.success("Channel added");
      onClose();
    } catch (e) { toast.error("Failed"); }
    finally { setBusy(false); }
  };

  const fields = {
    slack:    [{k:"webhook_url", label:"SLACK WEBHOOK URL", placeholder:"https://hooks.slack.com/services/…"}],
    webhook:  [{k:"url", label:"POST URL", placeholder:"https://api.yourapp.com/hook"}, {k:"secret", label:"HMAC SECRET (OPTIONAL)"}],
    whatsapp: [{k:"to", label:"WHATSAPP NUMBER", placeholder:"+91 98xxx xxxxx"}],
    email:    [{k:"to", label:"EMAIL", placeholder:"you@company.com"}],
    sms:      [{k:"to", label:"PHONE", placeholder:"+91 98xxx xxxxx"}],
    voice:    [{k:"to", label:"PHONE (VOICE CALL)", placeholder:"+91 98xxx xxxxx"}],
    teams:    [{k:"url", label:"TEAMS WEBHOOK URL"}],
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur grid place-items-center p-4">
      <div className="nv-card p-6 w-full max-w-lg relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[#737373] hover:text-white" data-testid="close-add-channel"><X size={16}/></button>
        <h2 className="font-display font-black text-2xl tracking-tight mb-4">Add channel</h2>
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mb-5">
          {KINDS.map((k)=>(
            <button key={k.key} type="button" onClick={()=>{setKind(k.key); setConfig({});}}
              className={`nv-card p-3 text-center ${kind===k.key ? "border-[#ccff00]/60" : ""}`}
              data-testid={`kind-${k.key}`}
            >
              <k.icon size={18} className="mx-auto mb-1" strokeWidth={1.5}/>
              <div className="text-[10px] font-mono tracking-widest">{k.label.toUpperCase()}</div>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-[#a3a3a3] mb-4">{K?.desc}</p>
        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">NAME</span>
            <input required value={name} onChange={(e)=>setName(e.target.value)} placeholder={`My ${kind} channel`} className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none" data-testid="ch-name"/>
          </label>
          {fields[kind].map((f)=>(
            <label key={f.k} className="block">
              <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">{f.label}</span>
              <input value={config[f.k] || ""} onChange={(e)=>setConfig({...config, [f.k]: e.target.value})}
                placeholder={f.placeholder}
                className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none"
                data-testid={`ch-${f.k}`}/>
            </label>
          ))}
          <button disabled={busy} className="nv-hard-btn w-full text-sm mt-3" data-testid="submit-channel">{busy?"…":"Add channel"}</button>
        </form>
      </div>
    </div>
  );
}
