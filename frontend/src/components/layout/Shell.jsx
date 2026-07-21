import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard, Cctv, ScanEye, Radio, Bell, KeyRound,
  Wallet, LineChart, Settings, LogOut, Eye
} from "lucide-react";

const NAV = [
  { to: "/app", icon: LayoutDashboard, label: "Overview", end: true, id: "nav-overview" },
  { to: "/app/cameras", icon: Cctv, label: "Cameras", id: "nav-cameras" },
  { to: "/app/detections", icon: ScanEye, label: "Detections", id: "nav-detections" },
  { to: "/app/events", icon: Radio, label: "Events & Memory", id: "nav-events" },
  { to: "/app/alerts", icon: Bell, label: "Alerts", id: "nav-alerts" },
  { to: "/app/api", icon: KeyRound, label: "API Keys", id: "nav-api" },
  { to: "/app/billing", icon: Wallet, label: "Credits", id: "nav-billing" },
  { to: "/app/analytics", icon: LineChart, label: "Analytics", id: "nav-analytics" },
  { to: "/app/settings", icon: Settings, label: "Settings", id: "nav-settings" },
];

export default function Shell({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="nv-grain min-h-screen flex text-[15px]">
      <aside className="w-60 shrink-0 border-r border-[#262626] bg-[#0a0a0a] flex flex-col relative z-10">
        <div className="px-5 py-5 border-b border-[#262626] flex items-center gap-2">
          <div className="w-7 h-7 grid place-items-center bg-[#ccff00] text-black">
            <Eye size={16} strokeWidth={2.5} />
          </div>
          <div>
            <div className="font-display font-black text-[17px] leading-none tracking-tight">NVISION</div>
            <div className="text-[10px] text-[#737373] font-mono tracking-widest mt-1">v0.1 · BETA</div>
          </div>
        </div>
        <nav className="flex-1 py-3">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={n.id}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-[13px] transition-colors border-l-2 ${
                  isActive
                    ? "border-[#ccff00] bg-[#ccff00]/5 text-white"
                    : "border-transparent text-[#a3a3a3] hover:text-white hover:bg-white/[0.02]"
                }`
              }
            >
              <n.icon size={16} strokeWidth={1.5} />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-[#262626] p-3">
          <div className="flex items-center gap-3 px-2 py-2">
            <div className="w-8 h-8 grid place-items-center bg-[#1e1e1e] border border-[#262626] font-mono text-xs">
              {(user?.name || "?")[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[12px] truncate">{user?.name}</div>
              <div className="text-[10px] text-[#737373] font-mono truncate">{user?.email}</div>
            </div>
            <button
              data-testid="logout-btn"
              onClick={() => { logout(); nav("/"); }}
              className="p-1.5 text-[#737373] hover:text-[#ff3366] transition-colors"
              title="Log out"
            >
              <LogOut size={14} />
            </button>
          </div>
          <div className="mt-1 px-2 pt-2 border-t border-[#262626]">
            <div className="flex justify-between items-baseline">
              <span className="text-[10px] text-[#737373] tracking-widest">CREDITS</span>
              <span data-testid="credits-balance" className="font-mono text-[13px] text-[#ccff00]">{user?.credits ?? 0}</span>
            </div>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0 relative z-10">{children}</main>
    </div>
  );
}
