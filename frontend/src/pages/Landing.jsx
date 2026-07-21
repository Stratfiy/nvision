import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Cctv, Brain, Bell, Zap, ShieldCheck, Terminal } from "lucide-react";

const Feature = ({ icon: Icon, title, desc }) => (
  <div className="nv-card p-6">
    <Icon size={22} strokeWidth={1.5} className="text-[#ccff00] mb-3" />
    <div className="font-display text-[17px] font-bold mb-2">{title}</div>
    <div className="text-[13px] text-[#a3a3a3] leading-relaxed">{desc}</div>
  </div>
);

export default function Landing() {
  return (
    <div className="nv-grain min-h-screen relative">
      {/* Nav */}
      <div className="sticky top-0 z-20 backdrop-blur-xl bg-[#050505]/70 border-b border-[#262626]">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-[#ccff00] grid place-items-center"><Cctv size={14} className="text-black" strokeWidth={2.5}/></div>
            <span className="font-display font-black tracking-tight">NVISION</span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login" data-testid="nav-login" className="text-[13px] text-[#a3a3a3] hover:text-white">Log in</Link>
            <Link to="/signup" data-testid="nav-signup" className="nv-hard-btn text-[13px]">Start free →</Link>
          </div>
        </div>
      </div>

      {/* Hero */}
      <div className="max-w-6xl mx-auto px-6 pt-20 pb-16 relative">
        <div className="inline-flex items-center gap-2 border border-[#262626] px-3 py-1 mb-6">
          <span className="w-1.5 h-1.5 nv-live-dot rounded-full" />
          <span className="font-mono text-[11px] tracking-widest text-[#a3a3a3]">PRIVATE BETA · 500 FREE CREDITS</span>
        </div>
        <h1 className="font-display font-black text-5xl md:text-6xl lg:text-7xl leading-[0.95] tracking-tighter max-w-4xl">
          Give your cameras<br/>
          <span className="text-[#ccff00]">memory</span> and a <span className="text-[#ccff00]">phone number.</span>
        </h1>
        <p className="mt-8 max-w-2xl text-[17px] text-[#a3a3a3] leading-relaxed">
          Connect any RTSP/IP camera. Describe what to watch for in plain language. Get real-time alerts on WhatsApp,
          Slack, webhook, or a phone call — with a searchable text memory of everything your cameras have ever seen.
        </p>
        <div className="mt-10 flex items-center gap-4">
          <Link to="/signup" data-testid="hero-start" className="nv-hard-btn inline-flex items-center gap-2 text-sm">
            Start free — 500 credits <ArrowRight size={16} />
          </Link>
          <Link to="/login" data-testid="hero-login" className="text-[13px] text-[#a3a3a3] hover:text-white font-mono tracking-widest">
            HAVE AN ACCOUNT? →
          </Link>
        </div>

        {/* code-ish preview */}
        <div className="mt-16 nv-card p-0 overflow-hidden">
          <div className="border-b border-[#262626] px-4 py-2 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[#ff3366]" />
            <div className="w-2 h-2 rounded-full bg-[#ffb800]" />
            <div className="w-2 h-2 rounded-full bg-[#ccff00]" />
            <span className="ml-3 font-mono text-[11px] text-[#737373]">nvision · detection-builder</span>
          </div>
          <div className="p-6 font-mono text-[13px] leading-relaxed">
            <div className="text-[#737373]"># Detection prompt</div>
            <div className="text-white">&quot;Alert if a worker is <span className="text-[#ccff00]">not wearing a helmet</span> in Zone A&quot;</div>
            <div className="mt-4 text-[#737373]"># Channels</div>
            <div><span className="text-[#00b2ff]">whatsapp</span>: <span className="text-[#a3a3a3]">+91-98xxx-42111</span></div>
            <div><span className="text-[#00b2ff]">slack</span>: <span className="text-[#a3a3a3]">#safety-alerts</span></div>
            <div><span className="text-[#00b2ff]">webhook</span>: <span className="text-[#a3a3a3]">https://api.factory.io/hook</span></div>
            <div className="mt-4 text-[#737373]"># Memory — ask anything, later</div>
            <div className="text-white">&quot;was there anyone at the gate at <span className="text-[#ccff00]">5pm yesterday</span>?&quot;</div>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="max-w-6xl mx-auto px-6 py-16 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Feature icon={Cctv} title="Any camera, any prompt" desc="RTSP, IP, or snapshot URL. Write detection rules in plain English — no ML training needed." />
        <Feature icon={Brain} title="Text memory of every event" desc="Every frame becomes a timestamped caption. Ask 'what happened at 3pm?' in natural language." />
        <Feature icon={Bell} title="Alerts on your channel" desc="WhatsApp, Slack, Teams, Email, Webhook, or a phone call with TTS. Escalation chains built in." />
        <Feature icon={Zap} title="Motion-gated to stay cheap" desc="AI only wakes on movement. Blended cost stays under ₹250/camera/month at launch scale." />
        <Feature icon={ShieldCheck} title="India-first & DPDP-aware" desc="Face recognition off by default. Privacy masks. DLT-ready SMS templates. GST invoicing." />
        <Feature icon={Terminal} title="Developer-first API" desc="REST + webhooks with HMAC signatures. BYO OpenAI/Anthropic/Twilio keys. Full transparency." />
      </div>

      {/* CTA */}
      <div className="max-w-4xl mx-auto px-6 py-20 text-center">
        <h2 className="font-display font-black text-4xl md:text-5xl tracking-tighter">
          First alert in under <span className="text-[#ccff00]">10 minutes.</span>
        </h2>
        <p className="mt-6 text-[15px] text-[#a3a3a3]">
          500 credits free at signup. No card required. Bring your own model & telephony keys anytime to cut costs.
        </p>
        <Link to="/signup" data-testid="cta-start" className="nv-hard-btn inline-flex items-center gap-2 mt-8 text-sm">
          Start free <ArrowRight size={16} />
        </Link>
      </div>

      <div className="border-t border-[#262626] py-6 text-center font-mono text-[11px] text-[#525252] tracking-widest">
        © 2026 NAUTOMATION LABS · NVISION v0.1 BETA
      </div>
    </div>
  );
}
