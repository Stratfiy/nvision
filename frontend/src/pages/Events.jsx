import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Search, ThumbsUp, ThumbsDown, Check } from "lucide-react";
import { toast } from "sonner";

export default function Events() {
  const [events, setEvents] = useState([]);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [onlyMatches, setOnlyMatches] = useState(false);

  const load = () => {
    api.get(`/events?limit=100${onlyMatches ? "&only_matches=true" : ""}`).then((r) => setEvents(r.data));
  };
  useEffect(() => { load(); }, [onlyMatches]);

  const ask = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setAnswer(null);
    try {
      const r = await api.post("/memory/query", { query, limit: 8 });
      setAnswer(r.data);
    } catch (e) {
      toast.error("Query failed");
    } finally { setBusy(false); }
  };

  const feedback = async (id, correct) => {
    await api.post("/events/feedback", { event_id: id, correct });
    setEvents((es) => es.map((e) => e.id === id ? { ...e, feedback: correct ? "correct" : "false_alarm" } : e));
    toast.success("Thanks — improves precision");
  };

  const ack = async (id) => {
    await api.post(`/events/${id}/ack`);
    setEvents((es) => es.map((e) => e.id === id ? { ...e, acknowledged: true } : e));
  };

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="font-display font-black text-4xl tracking-tighter">Events &amp; Memory</h1>
        <p className="text-[13px] text-[#a3a3a3] mt-1">Every frame becomes searchable text. Ask your cameras anything.</p>
      </div>

      {/* Memory search — hero */}
      <form onSubmit={ask} className="nv-card p-4 mb-6">
        <div className="flex items-center gap-3">
          <Search size={16} className="text-[#ccff00]"/>
          <input
            value={query}
            onChange={(e)=>setQuery(e.target.value)}
            placeholder="Ask your cameras… e.g. 'was there anyone at the gate at 5pm yesterday?'"
            className="flex-1 bg-transparent border-none outline-none font-mono text-[13px] text-white placeholder:text-[#525252]"
            data-testid="memory-search"
          />
          <button disabled={busy || !query.trim()} className="nv-hard-btn text-[12px] py-1.5 px-3" data-testid="memory-ask">
            {busy ? "…" : "Ask →"}
          </button>
        </div>
      </form>

      {answer && (
        <div className="nv-card p-5 mb-6 border-[#ccff00]/40" data-testid="memory-answer">
          <div className="text-[10px] font-mono tracking-widest text-[#ccff00] mb-2">MEMORY · ANSWER</div>
          <p className="text-[14px] leading-relaxed">{answer.answer}</p>
          {answer.citations?.length > 0 && (
            <div className="mt-4 border-t border-[#262626] pt-3">
              <div className="text-[10px] font-mono tracking-widest text-[#a3a3a3] mb-2">CITED EVENTS</div>
              <ul className="space-y-1">
                {answer.citations.slice(0, 5).map((c) => (
                  <li key={c.id} className="text-[12px] flex items-baseline gap-2 font-mono">
                    <span className="text-[#737373]">{c.timestamp?.slice(0,19).replace("T"," ")}</span>
                    <span className="text-[#a3a3a3]">{c.camera_name}</span>
                    <span className="text-[#e5e5e5]">— {c.caption}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4">
        <button onClick={()=>setOnlyMatches(false)} className={`text-[11px] font-mono tracking-widest px-3 py-1.5 border ${!onlyMatches ? "border-[#ccff00] text-[#ccff00]" : "border-[#262626] text-[#a3a3a3]"}`} data-testid="filter-all">ALL EVENTS</button>
        <button onClick={()=>setOnlyMatches(true)} className={`text-[11px] font-mono tracking-widest px-3 py-1.5 border ${onlyMatches ? "border-[#ccff00] text-[#ccff00]" : "border-[#262626] text-[#a3a3a3]"}`} data-testid="filter-matches">MATCHES ONLY</button>
      </div>

      {/* Feed */}
      {events.length === 0 ? (
        <div className="nv-card p-12 text-center text-[13px] text-[#737373]">No events yet. Run a detection to populate memory.</div>
      ) : (
        <div className="space-y-2">
          {events.map((e) => (
            <div key={e.id} className={`nv-card p-4 ${e.match ? "border-[#ff3366]/30" : ""}`} data-testid={`event-${e.id}`}>
              <div className="flex items-start gap-4">
                <div className="text-center">
                  <div className={`inline-block w-2 h-2 rounded-full ${e.match ? "bg-[#ff3366]" : "bg-[#525252]"}`}/>
                  <div className="text-[10px] font-mono text-[#737373] mt-2 whitespace-nowrap">{e.timestamp?.slice(11,19)}</div>
                  <div className="text-[9px] font-mono text-[#525252]">{e.timestamp?.slice(0,10)}</div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-display font-bold text-[14px]">{e.detection_name}</span>
                    <span className="font-mono text-[10px] text-[#a3a3a3]">· {e.camera_name}</span>
                    <span className={`font-mono text-[10px] px-1.5 py-0.5 ${e.match ? "bg-[#ff3366]/10 text-[#ff3366]" : "bg-[#262626] text-[#a3a3a3]"}`}>
                      {e.match ? "MATCH" : "no-match"} · {(e.confidence*100).toFixed(0)}%
                    </span>
                    {e.feedback === "correct" && <span className="font-mono text-[10px] text-[#ccff00]">✓ CORRECT</span>}
                    {e.feedback === "false_alarm" && <span className="font-mono text-[10px] text-[#ffb800]">FALSE ALARM</span>}
                    {e.acknowledged && <span className="font-mono text-[10px] text-[#a3a3a3]">ACK</span>}
                  </div>
                  <p className="text-[13px] text-[#e5e5e5]">{e.caption}</p>
                  {e.objects?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {e.objects.map((o,i)=><span key={i} className="font-mono text-[10px] px-1.5 py-0.5 border border-[#262626] text-[#737373]">{o}</span>)}
                    </div>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <button onClick={()=>feedback(e.id, true)} className="text-[#737373] hover:text-[#ccff00] p-1" data-testid={`up-${e.id}`}><ThumbsUp size={14}/></button>
                  <button onClick={()=>feedback(e.id, false)} className="text-[#737373] hover:text-[#ff3366] p-1" data-testid={`down-${e.id}`}><ThumbsDown size={14}/></button>
                  {e.match && !e.acknowledged && (
                    <button onClick={()=>ack(e.id)} className="text-[#737373] hover:text-[#00b2ff] p-1" title="Acknowledge" data-testid={`ack-${e.id}`}><Check size={14}/></button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
