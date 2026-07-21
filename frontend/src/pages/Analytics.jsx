import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, BarChart, Bar } from "recharts";

const Card = ({ children, className="" }) => <div className={`nv-card p-5 ${className}`}>{children}</div>;

export default function Analytics() {
  const [d, setD] = useState(null);
  useEffect(()=>{ api.get("/analytics/summary").then((r)=>setD(r.data)); }, []);

  if (!d) return <div className="p-8 text-[#737373]">Loading…</div>;

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="font-display font-black text-4xl tracking-tighter">Analytics</h1>
        <p className="text-[13px] text-[#a3a3a3] mt-1">7-day event trends and precision.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Card><div className="text-[10px] tracking-widest text-[#737373] font-mono">EVENTS</div><div className="font-display font-black text-3xl mt-1">{d.totals.events}</div></Card>
        <Card><div className="text-[10px] tracking-widest text-[#737373] font-mono">MATCHES</div><div className="font-display font-black text-3xl mt-1 text-[#ff3366]">{d.totals.matches}</div></Card>
        <Card><div className="text-[10px] tracking-widest text-[#737373] font-mono">PRECISION</div><div className="font-display font-black text-3xl mt-1 text-[#ccff00]">{d.precision != null ? `${(d.precision*100).toFixed(0)}%` : "—"}</div></Card>
        <Card><div className="text-[10px] tracking-widest text-[#737373] font-mono">CAMERAS</div><div className="font-display font-black text-3xl mt-1">{d.totals.cameras}</div></Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-3">
        <Card>
          <div className="font-display font-bold mb-3">Events by day (7d)</div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={d.daily}>
                <XAxis dataKey="day" stroke="#525252" tick={{fontSize:10, fontFamily:'JetBrains Mono'}}/>
                <YAxis stroke="#525252" tick={{fontSize:10, fontFamily:'JetBrains Mono'}}/>
                <Tooltip contentStyle={{background:'#121212', border:'1px solid #262626', fontSize:'12px', fontFamily:'JetBrains Mono'}}/>
                <Line type="monotone" dataKey="events" stroke="#ccff00" strokeWidth={2} dot={{r:3, fill:"#ccff00"}}/>
                <Line type="monotone" dataKey="matches" stroke="#ff3366" strokeWidth={2} dot={{r:3, fill:"#ff3366"}}/>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <div className="font-display font-bold mb-3">Busiest cameras</div>
          {d.busiest_cameras.length === 0 ? (
            <div className="text-[13px] text-[#737373] py-12 text-center">No data yet.</div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.busiest_cameras}>
                  <XAxis dataKey="camera" stroke="#525252" tick={{fontSize:10, fontFamily:'JetBrains Mono'}}/>
                  <YAxis stroke="#525252" tick={{fontSize:10, fontFamily:'JetBrains Mono'}}/>
                  <Tooltip contentStyle={{background:'#121212', border:'1px solid #262626', fontSize:'12px', fontFamily:'JetBrains Mono'}}/>
                  <Bar dataKey="events" fill="#ccff00"/>
                  <Bar dataKey="matches" fill="#ff3366"/>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4 grid md:grid-cols-2 gap-3">
        <Card>
          <div className="font-display font-bold mb-3">Feedback quality</div>
          <div className="font-mono text-[12px] space-y-1.5">
            <div className="flex justify-between"><span>Correct</span><span className="text-[#ccff00]">{d.correct}</span></div>
            <div className="flex justify-between"><span>False alarms</span><span className="text-[#ff3366]">{d.false_alarm}</span></div>
            <div className="flex justify-between border-t border-[#262626] pt-2 mt-2"><span>Labeled total</span><span>{d.correct + d.false_alarm}</span></div>
          </div>
        </Card>
        <Card>
          <div className="font-display font-bold mb-3">Cost projection</div>
          <p className="text-[12px] text-[#a3a3a3]">Motion-gated pipeline keeps blended infra cost under ₹250/camera/month at launch scale.
            Provide OpenAI/Anthropic/Gemini keys in <span className="font-mono text-[#ccff00]">Settings</span> to bill vision usage directly to your provider account.</p>
        </Card>
      </div>
    </div>
  );
}
