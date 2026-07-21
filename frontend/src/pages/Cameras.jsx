import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { Plus, Cctv, Trash2, X, ImagePlus } from "lucide-react";
import { toast } from "sonner";

const DEMO_SNAPSHOTS = [
  "https://images.pexels.com/photos/36162857/pexels-photo-36162857.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
  "https://images.unsplash.com/photo-1606206873764-fd15e242df52?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDJ8MHwxfHNlYXJjaHwyfHxtYW51ZmFjdHVyaW5nJTIwcXVhbGl0eSUyMGNvbnRyb2wlMjBjYW1lcmF8ZW58MHx8fHwxNzg0NjE0OTQyfDA&ixlib=rb-4.1.0&q=85",
];

export default function Cameras() {
  const [cams, setCams] = useState([]);
  const [showAdd, setShowAdd] = useState(false);

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
          <p className="text-[13px] text-[#a3a3a3] mt-1">RTSP, IP, or snapshot URL. Upload a clip works too.</p>
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
              <div className="aspect-video bg-[#0a0a0a] relative nv-scanlines">
                {c.snapshot_url ? (
                  <img src={c.snapshot_url} alt={c.name} className="w-full h-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}}/>
                ) : (
                  <div className="w-full h-full grid place-items-center text-[#525252]"><Cctv size={30} strokeWidth={1.2}/></div>
                )}
                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 backdrop-blur px-2 py-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${c.status==="online" ? "nv-live-dot" : "bg-[#525252]"}`} />
                  <span className="font-mono text-[10px] tracking-widest">{c.status?.toUpperCase()}</span>
                </div>
                <button
                  onClick={()=>del(c.id)}
                  className="absolute top-2 right-2 p-1.5 bg-black/60 backdrop-blur text-[#a3a3a3] hover:text-[#ff3366] opacity-0 group-hover:opacity-100 transition-opacity"
                  data-testid={`del-cam-${c.id}`}
                >
                  <Trash2 size={13}/>
                </button>
              </div>
              <Link to={`/app/detections?camera=${c.id}`} className="block p-4">
                <div className="font-display font-bold">{c.name}</div>
                <div className="text-[11px] font-mono text-[#737373] mt-1 truncate">{c.rtsp_url || c.snapshot_url || "—"}</div>
                <div className="text-[10px] text-[#a3a3a3] mt-2 tracking-widest">{c.site?.toUpperCase()} · {c.timezone}</div>
              </Link>
            </div>
          ))}
        </div>
      )}

      {showAdd && <AddCameraModal onClose={()=>{ setShowAdd(false); load(); }} />}
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
        <p className="text-[12px] text-[#a3a3a3] mb-5">RTSP is captured for Phase 2. For MVP, use a snapshot URL — a public image works fine for demo.</p>
        <form onSubmit={submit} className="space-y-3">
          <Field label="NAME" value={name} onChange={(e)=>setName(e.target.value)} required testid="cam-name" placeholder="Main gate" />
          <Field label="RTSP URL (OPTIONAL)" value={rtsp} onChange={(e)=>setRtsp(e.target.value)} testid="cam-rtsp" placeholder="rtsp://user:pass@ip:554/stream1" />
          <Field label="SNAPSHOT URL" value={snap} onChange={(e)=>setSnap(e.target.value)} testid="cam-snap" placeholder="https://…/frame.jpg" />
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

function Field({ label, testid, ...props }) {
  return (
    <label className="block">
      <span className="block text-[10px] tracking-widest text-[#a3a3a3] font-mono mb-1">{label}</span>
      <input data-testid={testid} className="w-full bg-[#050505] border border-[#262626] px-3 py-2 text-[13px] font-mono focus:border-[#ccff00] outline-none" {...props}/>
    </label>
  );
}
