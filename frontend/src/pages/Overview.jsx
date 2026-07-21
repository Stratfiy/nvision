import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { Cctv, ScanEye, Radio, TrendingUp, ArrowRight, Zap, Wallet } from "lucide-react";

const Stat = ({ label, value, sub, testid, accent }) => (
  <div className="nv-card p-5" data-testid={testid}>
    <div className="text-[10px] tracking-widest text-[#737373] font-mono">{label}</div>
    <div className={`font-display font-black text-3xl mt-2 ${accent ? "text-[#ccff00]" : ""}`}>{value}</div>
    {sub && <div className="text-[11px] text-[#a3a3a3] mt-1 font-mono">{sub}</div>}
  </div>
);

export default function Overview() {
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [credits, setCredits] = useState(null);
  const [cams, setCams] = useState([]);

  useEffect(() => {
    api.get("/analytics/summary").then((r) => setSummary(r.data)).catch(()=>{});
    api.get("/events?limit=8").then((r) => setEvents(r.data)).catch(()=>{});
    api.get("/credits").then((r) => setCredits(r.data)).catch(()=>{});
    api.get("/cameras").then((r) => setCams(r.data)).catch(()=>{});
  }, []);

  const t = summary?.totals || {};

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="font-display font-black text-4xl tracking-tighter">Overview</h1>
          <p className="text-[13px] text-[#a3a3a3] mt-1">Everything your cameras have seen.</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono text-[#737373]">
          <span className="w-1.5 h-1.5 nv-live-dot rounded-full" />
          <span>LIVE</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <Stat label="CAMERAS" value={t.cameras ?? "—"} testid="stat-cameras" />
        <Stat label="DETECTIONS" value={t.detections ?? "—"} testid="stat-detections" />
        <Stat label="MATCHES (ALL-TIME)" value={t.matches ?? "—"} accent testid="stat-matches" />
        <Stat label="CREDITS LEFT" value={credits?.balance ?? "—"} sub={credits?.days_left ? `~${credits.days_left} days at current burn` : "no burn yet"} testid="stat-credits" />
      </div>

      {/* Onboarding */}
      {cams.length === 0 && (
        <div className="nv-card p-6 mb-8 border-[#ccff00]/40" data-testid="onboarding-widget">
          <div className="text-[11px] tracking-widest text-[#ccff00] font-mono mb-2">GETTING STARTED · 0/3</div>
          <div className="font-display font-bold text-xl mb-2">First alert in under 10 minutes.</div>
          <ol className="text-[13px] text-[#a3a3a3] space-y-1 mb-4 list-decimal pl-5">
            <li>Add a camera (snapshot URL or upload image works for demo).</li>
            <li>Pick a detection template or write your own prompt.</li>
            <li>Add an alert channel (Slack or Webhook) and hit test.</li>
          </ol>
          <Link to="/app/cameras" data-testid="onboarding-add-cam" className="nv-hard-btn inline-flex items-center gap-2 text-[13px]">
            Add first camera <ArrowRight size={14} />
          </Link>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Recent events */}
        <div className="lg:col-span-2 nv-card">
          <div className="px-5 py-3 border-b border-[#262626] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio size={14} className="text-[#ccff00]" />
              <span className="font-display font-bold">Recent events</span>
            </div>
            <Link to="/app/events" data-testid="overview-events-all" className="text-[11px] font-mono tracking-widest text-[#a3a3a3] hover:text-white">ALL →</Link>
          </div>
          {events.length === 0 ? (
            <div className="p-10 text-center text-[13px] text-[#737373]">No events yet. Run a detection to see events here.</div>
          ) : (
            <ul>
              {events.map((e) => (
                <li key={e.id} className="px-5 py-3 border-b border-[#262626] last:border-none hover:bg-white/[0.02]">
                  <div className="flex items-baseline gap-3">
                    <span className={`w-1.5 h-1.5 rounded-full ${e.match ? "bg-[#ff3366]" : "bg-[#525252]"}`} />
                    <span className="font-mono text-[11px] text-[#737373]">{e.timestamp?.slice(11,19)}</span>
                    <span className="font-mono text-[11px] text-[#a3a3a3]">{e.camera_name}</span>
                    <span className="text-[13px] flex-1">{e.caption}</span>
                    <span className="font-mono text-[10px] text-[#737373]">{(e.confidence*100).toFixed(0)}%</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <div className="nv-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Wallet size={14} className="text-[#ccff00]" />
              <span className="font-display font-bold">Credit burn</span>
            </div>
            <div className="text-[11px] font-mono text-[#a3a3a3]">
              <div className="flex justify-between py-1"><span>BALANCE</span><span className="text-[#ccff00]">{credits?.balance ?? 0}</span></div>
              <div className="flex justify-between py-1"><span>LAST 7 DAYS</span><span>-{credits?.burn_7d ?? 0}</span></div>
              <div className="flex justify-between py-1"><span>DAILY BURN</span><span>{credits?.daily_burn ?? 0}/day</span></div>
              <div className="flex justify-between py-1"><span>PROJECTION</span><span>{credits?.days_left ? `${credits.days_left}d` : "—"}</span></div>
            </div>
            <Link to="/app/billing" data-testid="overview-topup" className="mt-4 inline-flex items-center gap-1 text-[12px] text-[#ccff00] hover:underline">Top up →</Link>
          </div>

          <div className="nv-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp size={14} className="text-[#ccff00]" />
              <span className="font-display font-bold">Precision</span>
            </div>
            <div className="font-display font-black text-3xl">
              {summary?.precision != null ? `${(summary.precision*100).toFixed(0)}%` : "—"}
            </div>
            <div className="text-[11px] text-[#737373] mt-1 font-mono">
              from {(summary?.correct ?? 0) + (summary?.false_alarm ?? 0)} labeled events
            </div>
          </div>

          <div className="nv-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={14} className="text-[#ccff00]" />
              <span className="font-display font-bold">Quick jump</span>
            </div>
            <div className="space-y-2 text-[13px]">
              <Link to="/app/cameras" className="block text-[#a3a3a3] hover:text-white" data-testid="qj-cams">→ Cameras ({t.cameras ?? 0})</Link>
              <Link to="/app/detections" className="block text-[#a3a3a3] hover:text-white" data-testid="qj-dets">→ Detections ({t.detections ?? 0})</Link>
              <Link to="/app/alerts" className="block text-[#a3a3a3] hover:text-white" data-testid="qj-alerts">→ Alert channels</Link>
              <Link to="/app/api" className="block text-[#a3a3a3] hover:text-white" data-testid="qj-api">→ API keys & webhooks</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
