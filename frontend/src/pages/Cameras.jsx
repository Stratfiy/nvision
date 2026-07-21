import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { Plus, Cctv, Trash2, X, Layers, Pencil, Play } from "lucide-react";
import { toast } from "sonner";
import ZoneEditor from "@/components/ZoneEditor";

const DEMO_SNAPSHOTS = [
  "https://images.pexels.com/photos/36162857/pexels-photo-36162857.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
  "https://images.unsplash.com/photo-1606206873764-fd15e242df52?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDJ8MHwxfHNlYXJjaHwyfHxtYW51ZmFjdHVyaW5nJTIwcXVhbGl0eSUyMGNvbnRyb2wlMjBjYW1lcmF8ZW58MHx8fHwxNzg0NjE0OTQyfDA&ixlib=rb-4.1.0&q=85",
];

export default function Cameras() {
  const [cams, setCams] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [zoneCam, setZoneCam] = useState(null);
  const [editCam, setEditCam] = useState(null);
  const [liveCam, setLiveCam] = useState(null);

  const load = () => api.get("/cameras").then((r) => setCams(r.data));
  useEffect(() => { load(); }, []);

  const del = async (id) => {
    if (!window.confirm("Delete this camera and its detections?")) return;
    await api.delete(`/cameras/${id}`);
    toast.success("Camera removed");
    load();
  };

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="font-display font-black text-4xl tracking-tighter">Cameras</h1>
          <p className="text-[13px] text-[#a3a3a3] mt-1">RTSP, IP, or snapshot URL. Draw zones to constrain detections to specific regions.</p>
        </div>
        <button data-testid="add-camera-btn" onClick={()=>setShowAdd(true)} className="nv-hard-btn inline-flex items-center gap-2 text-sm">
          <Plus size={14}/> Add camera
        </button>
      </div>

      {cams.length === 0 ? (
        <div className="nv-card p-12 text-center">
          <Cctv size={40} className="mx-auto text-[#525252] mb-4" strokeWidth={1.2}/>
          <div className="font-display font-bold text-xl mb-2">No cameras yet.</div>
          <div className="text-[13px] text-[#a3a3a3] mb-6">Add your first camera to start detecting.</div>
          <button data-testid="empty-add-camera" onClick={()=>setShowAdd(true)} className="nv-hard-btn text-sm">+ Add camera</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {cams.map((c) => (
            <div key={c.id} className="nv-card overflow-hidden relative group" data-testid={`camera-card-${c.id}`}>
              <div className="aspect-video bg-[#0a0a0a] relative nv-scanlines cursor-pointer" onClick={()=>setLiveCam(c)} data-testid={`live-cam-${c.id}`}>
                <CameraPreview camera={c} />
                <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
                  <div className="bg-[#ccff00] text-black rounded-full p-3"><Play size={20} fill="black"/></div>
                </div>
                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 backdrop-blur px-2 py-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${c.status==="online" ? "nv-live-dot" : "bg-[#525252]"}`} />
                  <span className="font-mono text-[10px] tracking-widest">{c.status?.toUpperCase()}</span>
                </div>
                {c.zones?.length > 0 && (
                  <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur px-2 py-0.5 flex items-center gap-1">
                    <Layers size={10} className="text-[#ccff00]"/>
                    <span className="font-mono text-[10px] text-[#ccff00]">{c.zones.length} zone{c.zones.length===1?"":"s"}</span>
                  </div>
                )}
                <button
                  onClick={()=>del(c.id)}
                  className="absolute top-2 right-2 p-1.5 bg-black/60 backdrop-blur text-[#a3a3a3] hover:text-[#ff3366] opacity-0 group-hover:opacity-100 transition-opacity"
                  data-testid={`del-cam-${c.id}`}
                >
                  <Trash2 size={13}/>
                </button>
              </div>
              <div className="p-4">
                <Link to={`/app/detections?camera=${c.id}`} className="block">
                  <div className="font-display font-bold hover:text-[#ccff00] transition-colors">{c.name}</div>
                  <div className="text-[11px] font-mono text-[#737373] mt-1 truncate">{c.rtsp_url || c.snapshot_url || "—"}</div>
                  <div className="text-[10px] text-[#a3a3a3] mt-2 tracking-widest">{c.site?.toUpperCase()} · {c.timezone}</div>
                </Link>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={()=>setLiveCam(c)}
                    className="border border-[#262626] hover:border-[#ccff00] text-[11px] font-mono tracking-widest text-[#a3a3a3] hover:text-[#ccff00] px-3 py-1.5 inline-flex items-center gap-1.5 transition-colors"
                    data-testid={`live-btn-${c.id}`}
                  >
                    <Play size={11}/> LIVE VIEW
                  </button>
                  <button
                    onClick={()=>setZoneCam(c)}
                    className="border border-[#262626] hover:border-[#ccff00] text-[11px] font-mono tracking-widest text-[#a3a3a3] hover:text-[#ccff00] px-3 py-1.5 inline-flex items-center gap-1.5 transition-colors"
                    data-testid={`zones-cam-${c.id}`}
                  >
                    <Layers size={11}/> {c.zones?.length ? "EDIT ZONES" : "DRAW ZONES"}
                  </button>
                  <button
                    onClick={()=>setEditCam(c)}
                    className="border border-[#262626] hover:border-[#ccff00] text-[11px] font-mono tracking-widest text-[#a3a3a3] hover:text-[#ccff00] px-3 py-1.5 inline-flex items-center gap-1.5 transition-colors"
                    data-testid={`edit-cam-${c.id}`}
                  >
                    <Pencil size={11}/> EDIT RTSP
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && <AddCameraModal onClose={()=>{ setShowAdd(false); load(); }} />}
      {liveCam && <LiveView camera={liveCam} onClose={()=>setLiveCam(null)} />}
      {editCam && <EditRtspModal camera={editCam} onClose={()=>{ setEditCam(null); load(); }} />}
      {zoneCam && <ZoneEditor camera={zoneCam} onClose={(changed)=>{ setZoneCam(null); if (changed) load(); }} />}
    </div>
  );
}

function AddCameraModal({ onClose }) {
  const [name, setName] = useState("");
  const [rtsp, setRtsp] = useState("");
  const [snap, setSnap] = useState("");
  const [site, setSite] = useState("Default");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/cameras", { name, rtsp_url: rtsp, snapshot_url: snap, site, tags: [], timezone: "UTC" });
      toast.success("Camera added");
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur grid place-items-center p-6">
      <div className="nv-card p-6 w-full max-w-lg relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[#737373] hover:text-white" data-testid="close-add-cam"><X size={16}/></button>
        <h2 className="font-display font-black text-2xl tracking-tight mb-1">Add camera</h2>
        <p className="text-[12px] text-[#a3a3a3] mb-5">Point NVision at a live RTSP stream — the ingestion worker connects, watches for motion, and runs your detections in real time. A snapshot URL is an optional fallback for manual "Run now" checks.</p>
        <form onSubmit={submit} className="space-y-3">
          <Field label="NAME" value={name} onChange={(e)=>setName(e.target.value)} required testid="cam-name" placeholder="Main gate" />
          <Field label="RTSP URL (LIVE STREAM)" value={rtsp} onChange={(e)=>setRtsp(e.target.value)} testid="cam-rtsp" placeholder="rtsp://user:pass@ip:554/stream1" />
          <Field label="SNAPSHOT URL (OPTIONAL FALLBACK)" value={snap} onChange={(e)=>setSnap(e.target.value)} testid="cam-snap" placeholder="https://…/frame.jpg" />
          <div className="flex flex-wrap gap-2">
            <span className="text-[10px] tracking-widest text-[#737373] font-mono">DEMO:</span>
            {DEMO_SNAPSHOTS.map((u,i)=>(
              <button key={i} type="button" onClick={()=>setSnap(u)} className="text-[10px] font-mono text-[#ccff00] hover:underline" data-testid={`demo-snap-${i}`}>use demo {i+1}</button>
            ))}
          </div>
          <Field label="SITE" value={site} onChange={(e)=>setSite(e.target.value)} testid="cam-site" />
          <button data-testid="submit-add-cam" disabled={busy} className="nv-hard-btn w-full text-sm mt-3">{busy ? "…" : "Add camera"}</button>
        </form>
      </div>
    </div>
  );
}

function LiveView({ camera, onClose }) {
  // Near-live player: rapidly refreshes the still the worker captures from the
  // RTSP stream (~2s cadence). Not full-motion video — the app is snapshot-based
  // by design. Poll a bit faster than the worker pushes so we always show latest.
  const [frame, setFrame] = useState(null);
  const [ts, setTs] = useState(null);
  const [status, setStatus] = useState("connecting");

  useEffect(() => {
    let alive = true;
    let misses = 0;
    const tick = () => api.get(`/cameras/${camera.id}/snapshot`)
      .then((r) => {
        if (!alive) return;
        misses = 0;
        if (r.data?.image_b64) { setFrame(`data:image/jpeg;base64,${r.data.image_b64}`); setTs(r.data.ts); setStatus("live"); }
      })
      .catch(() => { if (alive) { misses += 1; setStatus(misses > 2 ? "waiting" : status); } });
    tick();
    const t = setInterval(tick, 1500);
    return () => { alive = false; clearInterval(t); };
  }, [camera.id]);

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur grid place-items-center p-4" onClick={onClose}>
      <div className="nv-card w-full max-w-4xl relative" onClick={(e)=>e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3 text-[#737373] hover:text-white z-10" data-testid="close-live"><X size={16}/></button>
        <div className="px-5 py-3 border-b border-[#262626] flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full ${status==="live" ? "nv-live-dot" : "bg-[#ffb800]"}`} />
          <span className="font-display font-black text-lg tracking-tight">{camera.name}</span>
          <span className="font-mono text-[10px] tracking-widest text-[#a3a3a3]">{status==="live" ? "LIVE · ~2s SNAPSHOT" : "WAITING FOR STREAM"}</span>
        </div>
        <div className="bg-black aspect-video grid place-items-center overflow-hidden">
          {frame ? (
            <img src={frame} alt={camera.name} className="w-full h-full object-contain"/>
          ) : (
            <div className="text-center text-[#a3a3a3] p-8">
              <Cctv size={40} className="mx-auto mb-3 text-[#525252]" strokeWidth={1.2}/>
              <div className="text-[13px]">Waiting for the worker to capture a frame…</div>
              <div className="text-[11px] text-[#737373] mt-2">This appears within ~seconds once the camera is <span className="text-[#ccff00]">ONLINE</span>. If it never appears, the stream isn't connecting — check the RTSP URL.</div>
            </div>
          )}
        </div>
        <div className="px-5 py-2 border-t border-[#262626] flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#737373]">{ts ? `frame @ ${new Date(ts).toLocaleTimeString()}` : "—"}</span>
          <span className="font-mono text-[10px] text-[#737373]">Near-live snapshot view · full-motion video needs a streaming gateway</span>
        </div>
      </div>
    </div>
  );
}

function CameraPreview({ camera }) {
  // Show the latest still the worker captured from the RTSP stream, refreshing
  // periodically for a near-live view. Falls back to snapshot_url, then an icon.
  const [frame, setFrame] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.get(`/cameras/${camera.id}/snapshot`)
      .then((r) => { if (alive && r.data?.image_b64) setFrame(`data:image/jpeg;base64,${r.data.image_b64}`); })
      .catch(() => {});
    load();
    const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [camera.id]);

  const src = frame || camera.snapshot_url;
  if (src) {
    return <img src={src} alt={camera.name} className="w-full h-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}}/>;
  }
  return <div className="w-full h-full grid place-items-center text-[#525252]"><Cctv size={30} strokeWidth={1.2}/></div>;
}

function EditRtspModal({ camera, onClose }) {
  const [rtsp, setRtsp] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch(`/cameras/${camera.id}`, { rtsp_url: rtsp });
      toast.success("RTSP URL updated — the worker will reconnect shortly");
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur grid place-items-center p-6">
      <div className="nv-card p-6 w-full max-w-lg relative">
        <button onClick={onClose} className="absolute top-3 right-3 text-[#737373] hover:text-white" data-testid="close-edit-rtsp"><X size={16}/></button>
        <h2 className="font-display font-black text-2xl tracking-tight mb-1">Edit RTSP URL</h2>
        <p className="text-[12px] text-[#a3a3a3] mb-1">{camera.name}</p>
        <p className="text-[11px] font-mono text-[#737373] mb-5 truncate">current: {camera.rtsp_url || "—"}</p>
        <form onSubmit={submit} className="space-y-3">
          <Field label="NEW RTSP URL" value={rtsp} onChange={(e)=>setRtsp(e.target.value)} required testid="edit-cam-rtsp" placeholder="rtsp://user:pass@ip:554/stream1" />
          <button data-testid="submit-edit-rtsp" disabled={busy} className="nv-hard-btn w-full text-sm mt-3">{busy ? "…" : "Save"}</button>
        </form>
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
