import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Wallet, Zap, TrendingDown } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";

export default function Billing() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);
  const { refresh } = useAuth();

  const load = () => api.get("/credits").then((r)=>setData(r.data));
  useEffect(()=>{ load(); }, []);

  const openRazorpay = (order) => new Promise((resolve, reject) => {
    if (!window.Razorpay) {
      reject(new Error("Razorpay checkout script did not load."));
      return;
    }
    const options = {
      key: order.key_id,
      amount: order.amount,
      currency: order.currency,
      name: "NVision",
      description: `${order.credits.toLocaleString()} credits (${order.pack})`,
      order_id: order.order_id,
      handler: (resp) => resolve(resp),
      prefill: { name: order.user?.name || "", email: order.user?.email || "" },
      theme: { color: "#ccff00" },
      modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
    };
    const rzp = new window.Razorpay(options);
    rzp.on("payment.failed", (resp) => reject(new Error(resp.error?.description || "Payment failed")));
    rzp.open();
  });

  const topup = async (pack) => {
    setBusy(pack);
    try {
      // 1. create order
      const orderRes = await api.post("/credits/topup", { pack });
      // 2. open Razorpay Checkout
      const paid = await openRazorpay(orderRes.data);
      // 3. verify with backend
      const v = await api.post("/credits/verify", {
        razorpay_order_id: paid.razorpay_order_id,
        razorpay_payment_id: paid.razorpay_payment_id,
        razorpay_signature: paid.razorpay_signature,
      });
      toast.success(`+${v.data.credits_added} credits added`);
      await refresh();
      load();
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || "Failed";
      if (msg !== "Payment cancelled") toast.error(msg);
    } finally { setBusy(null); }
  };

  if (!data) return <div className="p-8 text-[#737373]">Loading…</div>;

  return (
    <div className="p-8 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="font-display font-black text-4xl tracking-tighter">Credits</h1>
        <p className="text-[13px] text-[#a3a3a3] mt-1">One credit meter · Razorpay checkout · BYO model/telephony keys to slash costs.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-3 mb-8">
        <div className="nv-card p-6 md:col-span-2">
          <div className="flex items-center gap-2 mb-3"><Wallet size={16} className="text-[#ccff00]"/><span className="font-display font-bold">Balance</span></div>
          <div className="font-display font-black text-6xl text-[#ccff00]" data-testid="credits-value">{data.balance}</div>
          <div className="text-[12px] text-[#a3a3a3] font-mono mt-3 flex gap-6 flex-wrap">
            <span>7d burn: <span className="text-white">{data.burn_7d}</span></span>
            <span>daily: <span className="text-white">{data.daily_burn}</span></span>
            <span>projection: <span className="text-white">{data.days_left ? `${data.days_left}d` : "—"}</span></span>
          </div>
        </div>
        <div className="nv-card p-6">
          <div className="flex items-center gap-2 mb-3"><Zap size={16} className="text-[#ccff00]"/><span className="font-display font-bold">Rates</span></div>
          <div className="text-[12px] font-mono space-y-1.5">
            <div className="flex justify-between"><span>VLM eval</span><span>{data.rates.vlm_eval} cr</span></div>
            <div className="flex justify-between"><span>Slack/webhook</span><span>0 cr</span></div>
            <div className="flex justify-between"><span>WhatsApp/SMS (BYO)</span><span>0 cr</span></div>
            <div className="flex justify-between border-t border-[#262626] pt-1.5 mt-1.5 text-[#737373]"><span>BYO keys</span><span>bypass platform fee</span></div>
          </div>
        </div>
      </div>

      <div className="mb-8">
        <div className="text-[11px] tracking-widest text-[#a3a3a3] font-mono mb-3">TOP UP · POWERED BY RAZORPAY</div>
        <div className="grid md:grid-cols-3 gap-3">
          {Object.entries(data.packs).map(([id, p])=>(
            <div key={id} className={`nv-card p-6 ${id==="growth" ? "border-[#ccff00]/50" : ""}`}>
              {id === "growth" && <div className="text-[10px] font-mono tracking-widest text-[#ccff00] mb-2">POPULAR</div>}
              <div className="font-display font-black text-2xl capitalize">{id}</div>
              <div className="mt-2 text-[13px] text-[#a3a3a3]">₹{p.amount_inr.toLocaleString()}</div>
              <div className="mt-4 font-display font-black text-3xl text-[#ccff00]">{p.credits.toLocaleString()}</div>
              <div className="text-[11px] font-mono text-[#737373]">credits</div>
              <button
                onClick={()=>topup(id)}
                disabled={busy===id}
                className="nv-hard-btn w-full mt-5 text-[13px]"
                data-testid={`topup-${id}`}
              >
                {busy===id ? "Opening…" : `Pay ₹${p.amount_inr.toLocaleString()} →`}
              </button>
            </div>
          ))}
        </div>
        <div className="text-[11px] text-[#737373] mt-3 font-mono">
          Test card: <span className="text-[#ccff00]">4111 1111 1111 1111</span> · any future date · any CVV · OTP <span className="text-[#ccff00]">any 6 digits</span>
        </div>
      </div>

      <div className="nv-card">
        <div className="px-5 py-3 border-b border-[#262626] font-display font-bold flex items-center gap-2"><TrendingDown size={14}/> Transactions</div>
        {data.transactions.length === 0 ? (
          <div className="p-8 text-center text-[13px] text-[#737373]">No transactions yet.</div>
        ) : (
          <table className="w-full text-[12px] font-mono">
            <thead className="text-[10px] tracking-widest text-[#737373]">
              <tr className="border-b border-[#262626]"><th className="text-left px-5 py-2">TIME</th><th className="text-left">REASON</th><th className="text-right px-5">DELTA</th></tr>
            </thead>
            <tbody>
              {data.transactions.map((t)=>(
                <tr key={t.id} className="border-b border-[#262626] last:border-none">
                  <td className="px-5 py-2 text-[#a3a3a3]">{t.ts?.slice(0,19).replace("T"," ")}</td>
                  <td className="text-[#e5e5e5]">{t.reason}</td>
                  <td className={`px-5 text-right ${t.delta > 0 ? "text-[#ccff00]" : "text-[#ff3366]"}`}>{t.delta > 0 ? "+" : ""}{t.delta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
