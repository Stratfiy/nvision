import React, { useEffect, useRef, useState } from "react";
import { X, Save, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

/**
 * Zone editor modal — click on the snapshot to add polygon vertices.
 * Double-click (or "Close polygon") to finalize a zone. Multiple zones supported.
 * Coordinates stored normalized 0-1.
 */
export default function ZoneEditor({ camera, onClose }) {
  const imgRef = useRef(null);
  const canvasRef = useRef(null);
  const [zones, setZones] = useState(camera.zones || []);
  const [current, setCurrent] = useState([]);            // in-progress polygon (px coords)
  const [dims, setDims] = useState({ w: 800, h: 450 });
  const [busy, setBusy] = useState(false);
  const [nextName, setNextName] = useState("Zone A");

  const STOCK = "https://images.pexels.com/photos/36162857/pexels-photo-36162857.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";
  const [bg, setBg] = useState(camera.snapshot_url || STOCK);
  const [liveFrame, setLiveFrame] = useState(false);

  // Prefer a real still captured from the RTSP stream by the worker.
  useEffect(() => {
    let alive = true;
    api.get(`/cameras/${camera.id}/snapshot`)
      .then((r) => { if (alive && r.data?.image_b64) { setBg(`data:image/jpeg;base64,${r.data.image_b64}`); setLiveFrame(true); } })
      .catch(() => {});
    return () => { alive = false; };
  }, [camera.id]);

  useEffect(() => { draw(); }, [zones, current, dims]);

  const onImgLoad = () => {
    if (imgRef.current) {
      setDims({ w: imgRef.current.clientWidth, h: imgRef.current.clientHeight });
    }
  };

  const onCanvasClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setCurrent((c) => [...c, [x, y]]);
  };

  const finishPolygon = () => {
    if (current.length < 3) { toast("Need at least 3 points"); return; }
    const norm = current.map(([x, y]) => [+(x / dims.w).toFixed(4), +(y / dims.h).toFixed(4)]);
    setZones((zs) => [...zs, { name: nextName, points: norm }]);
    setCurrent([]);
    setNextName(`Zone ${String.fromCharCode(65 + zones.length + 1)}`);
  };

  const undoPoint = () => setCurrent((c) => c.slice(0, -1));

  const removeZone = (i) => setZones((zs) => zs.filter((_, idx) => idx !== i));

  const draw = () => {
    const c = canvasRef.current;
    if (!c) return;
    c.width = dims.w; c.height = dims.h;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, dims.w, dims.h);
    // saved zones
    zones.forEach((z, idx) => {
      const pts = z.points.map(([x, y]) => [x * dims.w, y * dims.h]);
      if (pts.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      pts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
      ctx.closePath();
      ctx.fillStyle = "rgba(204,255,0,0.15)";
      ctx.fill();
      ctx.strokeStyle = "#ccff00";
      ctx.lineWidth = 2;
      ctx.stroke();
      // label
      const [lx, ly] = pts[0];
      ctx.fillStyle = "#ccff00";
      ctx.font = "12px 'JetBrains Mono', monospace";
      ctx.fillText(z.name || `Zone ${idx+1}`, lx + 4, ly + 14);
    });
    // in-progress
    if (current.length > 0) {
      ctx.beginPath();
      ctx.moveTo(current[0][0], current[0][1]);
      current.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
      ctx.strokeStyle = "#ff3366";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
      current.forEach(([x, y]) => {
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#ff3366";
        ctx.fill();
      });
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      await api.patch(`/cameras/${camera.id}`, { zones });
      toast.success("Zones saved");
      onClose(true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/80 backdrop-blur overflow-y-auto p-4">
      <div className="nv-card w-full max-w-4xl mx-auto relative">
        <button onClick={()=>onClose(false)} className="absolute top-3 right-3 text-[#737373] hover:text-white z-10" data-testid="close-zone-editor"><X size={16}/></button>
        <div className="px-5 py-3 border-b border-[#262626]">
          <div className="font-display font-black text-xl tracking-tight">Zone Editor · {camera.name}</div>
          <div className="text-[12px] text-[#a3a3a3] mt-1">
            Click to add points → &quot;Close polygon&quot; to save that zone. Detection only fires INSIDE zones.
            {liveFrame
              ? <span className="text-[#ccff00] ml-1">· live frame from stream</span>
              : <span className="text-[#ffb800] ml-1">· no live frame yet — showing placeholder (worker captures one within ~15s of connecting)</span>}
          </div>
        </div>

        <div className="p-5">
          <div className="relative inline-block w-full" style={{ maxWidth: 900 }}>
            <img
              ref={imgRef}
              src={bg}
              alt={camera.name}
              onLoad={onImgLoad}
              onError={(e)=>{e.currentTarget.src=STOCK;}}
              className="w-full block select-none"
              draggable={false}
            />
            <canvas
              ref={canvasRef}
              onClick={onCanvasClick}
              className="absolute inset-0 w-full h-full cursor-crosshair"
              data-testid="zone-canvas"
            />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <input
              value={nextName}
              onChange={(e)=>setNextName(e.target.value)}
              className="bg-[#050505] border border-[#262626] px-3 py-1.5 text-[12px] font-mono focus:border-[#ccff00] outline-none w-32"
              data-testid="zone-name"
            />
            <button onClick={finishPolygon} disabled={current.length < 3} className="nv-hard-btn text-[12px] py-1.5 px-3" data-testid="close-polygon">
              Close polygon ({current.length}pt)
            </button>
            <button onClick={undoPoint} disabled={current.length === 0} className="border border-[#262626] text-[12px] py-1.5 px-3 text-[#a3a3a3] hover:border-[#3a3a3a]">Undo point</button>
            <button onClick={()=>setCurrent([])} disabled={current.length === 0} className="border border-[#262626] text-[12px] py-1.5 px-3 text-[#a3a3a3] hover:border-[#3a3a3a]">Clear draft</button>
            <div className="flex-1"/>
            <button onClick={save} disabled={busy} className="nv-hard-btn text-[13px] inline-flex items-center gap-1" data-testid="save-zones">
              <Save size={12}/> {busy ? "…" : `Save ${zones.length} zone${zones.length===1?"":"s"}`}
            </button>
          </div>

          {zones.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {zones.map((z, i) => (
                <div key={i} className="flex items-center gap-2 border border-[#262626] px-2 py-1 text-[11px] font-mono">
                  <span className="text-[#ccff00]">{z.name}</span>
                  <span className="text-[#737373]">· {z.points.length} pts</span>
                  <button onClick={()=>removeZone(i)} className="text-[#a3a3a3] hover:text-[#ff3366]" data-testid={`del-zone-${i}`}><Trash2 size={11}/></button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
