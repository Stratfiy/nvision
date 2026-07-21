import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

import { AuthProvider, useAuth } from "@/lib/auth";
import Landing from "@/pages/Landing";
import { LoginPage, SignupPage } from "@/pages/AuthPages";
import Shell from "@/components/layout/Shell";
import Overview from "@/pages/Overview";
import Cameras from "@/pages/Cameras";
import Detections from "@/pages/Detections";
import Events from "@/pages/Events";
import Alerts from "@/pages/Alerts";
import ApiKeys from "@/pages/ApiKeys";
import Billing from "@/pages/Billing";
import Analytics from "@/pages/Analytics";
import Settings from "@/pages/Settings";

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen grid place-items-center text-[#737373] font-mono text-sm">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
};

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/app" element={<Protected><Overview /></Protected>} />
            <Route path="/app/cameras" element={<Protected><Cameras /></Protected>} />
            <Route path="/app/detections" element={<Protected><Detections /></Protected>} />
            <Route path="/app/events" element={<Protected><Events /></Protected>} />
            <Route path="/app/alerts" element={<Protected><Alerts /></Protected>} />
            <Route path="/app/api" element={<Protected><ApiKeys /></Protected>} />
            <Route path="/app/billing" element={<Protected><Billing /></Protected>} />
            <Route path="/app/analytics" element={<Protected><Analytics /></Protected>} />
            <Route path="/app/settings" element={<Protected><Settings /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace/>}/>
          </Routes>
        </BrowserRouter>
        <Toaster theme="dark" position="bottom-right" toastOptions={{
          style: { background: '#121212', border: '1px solid #262626', color: '#f5f5f5', borderRadius: '2px', fontFamily: 'IBM Plex Sans' }
        }}/>
      </AuthProvider>
    </div>
  );
}

export default App;
