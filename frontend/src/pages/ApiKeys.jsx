import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Plus, KeyRound, Trash2, Copy, Check } from "lucide-react";
import { toast } from "sonner";

export default function ApiKeys() {
  const [keys, setKeys] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [justCreated, setJustCreated] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = () => api.get("/api-keys").then((r)=>setKeys(r.data));
  useEffect(()=>{ load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    const name = e.target.name.value;
    const scope = e.target.scope.value;
    const r = await api.post("/api-keys", { name, scope });
    setJustCreated(r.data);
    setShowNew(false);
    load();
  };

  const del = async (id) => {
    if (!window.confirm("Revoke this key?")) return;
    await api.delete(`/api-keys/${id}`);
    load();
  };

  const copy = (v) => {
    navigator.clipboard.writeText(v);
    setCopied(true);
    setTimeout(()=>setCopied(false), 1500);
    toast.success("Copied");
  };

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="font-display font-black text-4xl tracking-tighter">API Keys</h1>
          <p className="text-[13px] text-[#a3a3a3] mt-1">Programmatic access to cameras, detections, events, and memory.</p>
        </div>
        <button onClick={()=>setShowNew(true)} className="nv-hard-btn inline-flex items-center gap-2 text-sm" data-testid="new-api-key">
          <Plus size={14}/> New key
        </button>
      </div>

      {justCreated && (
        <div className="nv-card p-5 mb-6 border-[#ccff00]/40" data-testid="new-key-banner">
          <div className="text-[10px] font-mono tracking-widest text-[#ccff00] mb-2">SAVE THIS KEY — SHOWN ONCE</div>
          <div className="flex items-center gap-2">
            <code className="font-mono text-[13px] flex-1 bg-[#050505] border border-[#262626] px-3 py-2 truncate">{justCreated.key}</code>
            <button onClick={()=>copy(justCreated.key)} className="nv-hard-btn text-[12px] px-3 py-2 inline-flex items-center gap-1">
              {copied ? <Check size={12}/> : <Copy size={12}/>} {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <button onClick={()=>setJustCreated(null)} className="mt-3 text-[11px] font-mono tracking-widest text-[#a3a3a3] hover:text-white">I&apos;VE SAVED IT →</button>
        </div>
      )}

      <div className="nv-card mb-8">
        {keys.length === 0 ? (
          <div className="p-10 text-center">
            <KeyRound size={36} className="mx-auto text-[#525252] mb-3" strokeWidth={1.2}/>
            <div className="font-display font-bold text-lg">No keys yet.</div>
          </div>
        ) : (
          <table className="w-full text-[13px]">
            <thead className="text-[10px] tracking-widest text-[#737373] font-mono">
              <tr className="border-b border-[#262626]">
                <th className="text-left px-5 py-2">NAME</th>
                <th className="text-left">PREFIX</th>
                <th className="text-left">SCOPE</th>
                <th className="text-left">CREATED</th>
                <th className="text-right px-5"></th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {keys.map((k)=>(
                <tr key={k.id} className="border-b border-[#262626] last:border-none">
                  <td className="px-5 py-3">{k.name}</td>
                  <td className="text-[#a3a3a3]">{k.key_prefix}…</td>
                  <td className="text-[#a3a3a3]">{k.scope}</td>
                  <td className="text-[#a3a3a3]">{k.created_at?.slice(0,10)}</td>
                  <td className="px-5 text-right">
                    <button onClick={()=>del(k.id)} className="text-[#a3a3a3] hover:text-[#ff3366]" data-testid={`del-key-${k.id}`}><Trash2 size={14}/></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* API docs snippet */}
      <div className="nv-card">
        <div className="px-5 py-3 border-b border-[#262626] font-display font-bold">Quickstart</div>
        <div className="p-5 space-y-4">
          <div>
            <div className="text-[10px] font-mono tracking-widest text-[#a3a3a3] mb-1"># 1. Trigger a detection on an image URL</div>
            <pre className="bg-[#050505] border border-[#262626] p-3 text-[12px] font-mono text-[#e5e5e5] overflow-x-auto">
{`curl -X POST ${window.location.origin.replace(/^https?:\/\/[^/]+/, "$&")}/api/analyze \\
  -H "Authorization: Bearer $NV_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"detection_id":"det_...", "image_url":"https://…/frame.jpg"}'`}
            </pre>
          </div>
          <div>
            <div className="text-[10px] font-mono tracking-widest text-[#a3a3a3] mb-1"># 2. Ask memory a question</div>
            <pre className="bg-[#050505] border border-[#262626] p-3 text-[12px] font-mono text-[#e5e5e5] overflow-x-auto">
{`curl -X POST /api/memory/query \\
  -d '{"query":"was anyone at the gate at 5pm yesterday?"}'`}
            </pre>
          </div>
          <div>
            <div className="text-[10px] font-mono tracking-widest text-[#a3a3a3] mb-1"># 3. Webhook payload (HMAC signed via X-NVision-Signature)</div>
            <pre className="bg-[#050505] border border-[#262626] p-3 text-[12px] font-mono text-[#e5e5e5] overflow-x-auto">
{`POST /your-endpoint
X-NVision-Signature: sha256=…
{
  "subject": "NVision Alert: PPE — Helmet Missing",
  "body": "[Zone A] Worker without helmet near press-1 (conf 82%)",
  "ts": "2026-02-15T18:30:00Z"
}`}
            </pre>
          </div>
        </div>
      </div>

      {showNew && (
        <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur grid place-items-center p-4">
          <form onSubmit={create} className="nv-card p-6 w-full max-w-md">
            <h3 className="font-display font-black text-xl mb-4">New API key</h3>
            <label className="block mb-3">
              <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">NAME</span>
              <input name="name" required placeholder="Production backend" className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none" data-testid="new-key-name"/>
            </label>
            <label className="block mb-4">
              <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">SCOPE</span>
              <select name="scope" className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none">
                <option value="full">Full access</option>
                <option value="read">Read only</option>
              </select>
            </label>
            <div className="flex gap-2">
              <button type="button" onClick={()=>setShowNew(false)} className="flex-1 border border-[#262626] py-2 text-[13px] hover:border-[#3a3a3a]">Cancel</button>
              <button className="nv-hard-btn flex-1 text-[13px]" data-testid="create-key-submit">Create</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
