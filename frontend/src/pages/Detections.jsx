import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Plus, X, ScanEye, Play, Trash2, Wand2, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";

export default function Detections() {
  const [params, setParams] = useSearchParams();
  const preselectCam = params.get("camera") || "";
  const [dets, setDets] = useState([]);
  const [cams, setCams] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [showBuilder, setShowBuilder] = useState(false);
  const [runningId, setRunningId] = useState(null);
  const [result, setResult] = useState(null);

  const load = async () => {
    const [a, b, c] = await Promise.all([
      api.get("/detections"),
      api.get("/cameras"),
      api.get("/templates"),
    ]);
    setDets(a.data);
    setCams(b.data);
    setTemplates(c.data);
  };
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (preselectCam && cams.length && !showBuilder) setShowBuilder(true);
  }, [preselectCam, cams.length]);

  const del = async (id) => {
    if (!window.confirm("Delete detection?")) return;
    await api.delete(`/detections/${id}`);
    load();
  };

  const runNow = async (det) => {
    setRunningId(det.id);
    setResult(null);
    try {
      const cam = cams.find((c) => c.id === det.camera_id);
      const r = await api.post("/analyze", {
        detection_id: det.id,
        image_url: cam?.snapshot_url || undefined,
      });
      setResult({ det, ...r.data });
      toast.success(r.data.event.match ? "Match detected → alerts dispatched" : "Analyzed — no match");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analyze failed");
    } finally { setRunningId(null); }
  };

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="font-display font-black text-4xl tracking-tighter">Detections</h1>
          <p className="text-[13px] text-[#a3a3a3] mt-1">Write a prompt. Optionally attach sample images. NVision watches.</p>
        </div>
        <button data-testid="new-detection-btn" onClick={()=>setShowBuilder(true)} className="nv-hard-btn inline-flex items-center gap-2 text-sm" disabled={cams.length===0}>
          <Plus size={14}/> New detection
        </button>
      </div>

      {cams.length === 0 && (
        <div className="nv-card p-4 text-[13px] text-[#ffb800] mb-6">Add a camera first from the Cameras page.</div>
      )}

      {dets.length === 0 ? (
        <div className="nv-card p-12 text-center">
          <ScanEye size={40} className="mx-auto text-[#525252] mb-4" strokeWidth={1.2}/>
          <div className="font-display font-bold text-xl mb-2">No detections yet.</div>
          <div className="text-[13px] text-[#a3a3a3] mb-6">Pick a template or write your own.</div>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-3">
          {dets.map((d) => (
            <div key={d.id} className="nv-card p-4 relative" data-testid={`detection-card-${d.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-display font-bold text-[16px]">{d.name}</div>
                  <div className="text-[11px] font-mono text-[#737373] mt-1">
                    {d.camera_name} · sens {d.sensitivity.toFixed(2)} · cooldown {d.cooldown_seconds ?? 120}s · fires {d.fires_count || 0}
                  </div>
                </div>
                <button onClick={()=>del(d.id)} className="text-[#737373] hover:text-[#ff3366]" data-testid={`del-det-${d.id}`}><Trash2 size={14}/></button>
              </div>
              <p className="text-[13px] text-[#a3a3a3] mt-3 leading-relaxed line-clamp-3">{d.prompt}</p>
              <div className="mt-4 flex items-center gap-2">
                <button
                  onClick={()=>runNow(d)}
                  disabled={runningId === d.id}
                  className="nv-hard-btn text-[12px] inline-flex items-center gap-1.5 py-1.5 px-3"
                  data-testid={`run-det-${d.id}`}
                >
                  <Play size={12} strokeWidth={2.5}/> {runningId === d.id ? "Analyzing…" : "Run now"}
                </button>
                {d.sample_images_b64?.length > 0 && (
                  <span className="font-mono text-[10px] text-[#737373] flex items-center gap-1"><ImageIcon size={11}/> {d.sample_images_b64.length} samples</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {result && <ResultModal r={result} onClose={()=>setResult(null)} />}
      {showBuilder && (
        <Builder cams={cams} templates={templates} preselectCam={preselectCam}
          onClose={()=>{ setShowBuilder(false); setParams({}); load(); }} />
      )}
    </div>
  );
}

function Builder({ cams, templates, preselectCam, onClose }) {
  const [cameraId, setCameraId] = useState(preselectCam || cams[0]?.id || "");
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [sensitivity, setSens] = useState(0.6);
  const [schedule, setSchedule] = useState("always");
  const [cooldown, setCooldown] = useState(120);
  const [samples, setSamples] = useState([]);
  const [busy, setBusy] = useState(false);

  const applyTemplate = (t) => {
    setName(t.name);
    setPrompt(t.prompt);
    setSens(t.sensitivity);
    setSchedule(t.schedule);
  };

  const onUpload = async (files) => {
    const arr = Array.from(files || []).slice(0, 6);
    const b64s = await Promise.all(arr.map((f) => new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result).split(",")[1]);
      r.onerror = rej;
      r.readAsDataURL(f);
    })));
    setSamples((s) => [...s, ...b64s].slice(0, 6));
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/detections", {
        camera_id: cameraId, name, prompt,
        sample_images_b64: samples,
        sensitivity, schedule,
        cooldown_seconds: Number(cooldown) || 120,
        zones: [], enabled: true,
      });
      toast.success("Detection created");
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur overflow-y-auto p-4">
      <div className="nv-card p-6 w-full max-w-3xl mx-auto relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[#737373] hover:text-white" data-testid="close-builder"><X size={16}/></button>
        <div className="flex items-center gap-2 mb-1"><Wand2 size={16} className="text-[#ccff00]"/> <span className="text-[11px] tracking-widest text-[#ccff00] font-mono">DETECTION BUILDER</span></div>
        <h2 className="font-display font-black text-2xl tracking-tight mb-5">Watch for something.</h2>

        <div className="text-[11px] tracking-widest text-[#a3a3a3] font-mono mb-2">TEMPLATES</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-5">
          {templates.map((t) => (
            <button key={t.id} type="button" onClick={()=>applyTemplate(t)} className="nv-card p-3 text-left hover:border-[#ccff00]/50" data-testid={`tmpl-${t.id}`}>
              <div className="font-display font-bold text-[13px]">{t.name}</div>
              <div className="text-[11px] text-[#737373] mt-0.5 font-mono">sens {t.sensitivity.toFixed(2)} · {t.schedule}</div>
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">CAMERA</span>
            <select value={cameraId} onChange={(e)=>setCameraId(e.target.value)} required className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none" data-testid="builder-camera">
              {cams.map((c)=><option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <Field label="DETECTION NAME" value={name} onChange={(e)=>setName(e.target.value)} required testid="builder-name"/>
          <label className="block">
            <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">PROMPT (PLAIN ENGLISH)</span>
            <textarea rows={4} value={prompt} onChange={(e)=>setPrompt(e.target.value)} required
              placeholder="e.g. Alert if a worker is not wearing a hard-hat in the loading bay."
              className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none"
              data-testid="builder-prompt"/>
          </label>

          <label className="block">
            <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">SENSITIVITY · {sensitivity.toFixed(2)}</span>
            <input type="range" min="0.3" max="0.95" step="0.05" value={sensitivity} onChange={(e)=>setSens(parseFloat(e.target.value))} className="w-full accent-[#ccff00]" data-testid="builder-sens"/>
          </label>

          <label className="block">
            <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">COOLDOWN (SECONDS) — SKIP RE-ANALYSIS AFTER A FIRE</span>
            <input type="number" min="0" step="1" value={cooldown} onChange={(e)=>setCooldown(e.target.value)}
              className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none"
              data-testid="builder-cooldown"/>
          </label>

          <label className="block">
            <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">SCHEDULE</span>
            <select value={schedule} onChange={(e)=>setSchedule(e.target.value)} className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none" data-testid="builder-schedule">
              <option value="always">Always</option>
              <option value="night">Night (10pm–6am)</option>
              <option value="business_hours">Business hours</option>
            </select>
          </label>

          <div>
            <div className="text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">SAMPLE IMAGES (OPTIONAL, MAX 6)</div>
            <div className="flex flex-wrap gap-2">
              {samples.map((s,i)=>(
                <div key={i} className="relative w-16 h-16 border border-[#262626]">
                  <img src={`data:image/jpeg;base64,${s}`} alt="" className="w-full h-full object-cover"/>
                  <button type="button" onClick={()=>setSamples(samples.filter((_,j)=>j!==i))} className="absolute -top-1 -right-1 bg-[#ff3366] w-4 h-4 grid place-items-center text-white text-[10px]">×</button>
                </div>
              ))}
              {samples.length < 6 && (
                <label className="w-16 h-16 border border-dashed border-[#262626] grid place-items-center cursor-pointer hover:border-[#ccff00]" data-testid="upload-samples">
                  <Plus size={16} className="text-[#737373]"/>
                  <input type="file" multiple accept="image/*" className="hidden" onChange={(e)=>onUpload(e.target.files)}/>
                </label>
              )}
            </div>
          </div>

          <button disabled={busy} className="nv-hard-btn w-full text-sm mt-3" data-testid="submit-builder">{busy ? "…" : "Create detection"}</button>
        </form>
      </div>
    </div>
  );
}

function ResultModal({ r, onClose }) {
  const ev = r.event;
  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur grid place-items-center p-4">
      <div className="nv-card p-6 w-full max-w-lg relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[#737373] hover:text-white"><X size={16}/></button>
        <div className={`text-[10px] font-mono tracking-widest mb-1 ${ev.match ? "text-[#ff3366]":"text-[#ccff00]"}`}>{ev.match ? "MATCH" : "NO MATCH"} · CONF {(ev.confidence*100).toFixed(0)}%</div>
        <h3 className="font-display font-black text-xl">{r.det.name}</h3>
        <p className="text-[13px] mt-3 text-[#e5e5e5] leading-relaxed">{ev.caption}</p>
        {ev.objects?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {ev.objects.map((o,i)=><span key={i} className="font-mono text-[10px] px-2 py-0.5 border border-[#262626] text-[#a3a3a3]">{o}</span>)}
          </div>
        )}
        {r.dispatched?.length > 0 && (
          <div className="mt-4 border-t border-[#262626] pt-3">
            <div className="text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-2">DISPATCHED</div>
            {r.dispatched.map((d,i)=>(
              <div key={i} className="text-[11px] font-mono flex justify-between">
                <span>{d.channel} · {d.kind}</span>
                <span className={d.status === "sent" ? "text-[#ccff00]" : d.status === "simulated" ? "text-[#ffb800]" : "text-[#ff3366]"}>{d.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, testid, ...props }) {
  return (
    <label className="block">
      <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">{label}</span>
      <input data-testid={testid} className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none" {...props}/>
    </label>
  );
}
