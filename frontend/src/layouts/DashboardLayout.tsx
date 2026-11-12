import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Outlet, NavLink, useNavigate, useLocation, Link } from 'react-router-dom';
import { ShieldCheck, FileText, FolderOpen, Search, LogOut, Activity, Users, FileSignature, AlertTriangle, ShieldAlert, Menu, X, BadgeCheck, Mail, Building2, KeyRound, Fingerprint, Radio, WifiOff, RefreshCw, BookOpen } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiClient, API_URL, HEALTH_URL } from '../api/client';
import { useSecurityFeed } from '../hooks/useSecurityFeed';

export const DashboardLayout = () => {
  const { user, mfaVerified, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [myCases, setMyCases] = useState<any[]>([]);
  const profileRef = useRef<HTMLDivElement>(null);
  const { connected, events, latest } = useSecurityFeed();
  const [alert, setAlert] = useState<any>(null);
  const navigate = useNavigate();

  const [backendDown, setBackendDown] = useState(false);
  const [rechecking, setRechecking] = useState(false);

  const checkBackend = useCallback(async () => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 4000);
    try {
      const res = await fetch(HEALTH_URL, { signal: controller.signal });
      setBackendDown(!res.ok);
    } catch {
      setBackendDown(true);
    } finally {
      window.clearTimeout(timer);
    }
  }, []);

  useEffect(() => {
    checkBackend();
    const id = window.setInterval(checkBackend, 10000);
    return () => window.clearInterval(id);
  }, [checkBackend]);

  const handleRecheck = async () => {
    setRechecking(true);
    await checkBackend();
    setRechecking(false);
  };

  useEffect(() => {
    if (!latest) return;
    if (latest.event === 'TAMPER_ALERT' || latest.event === 'TAMPER_RESOLVED') {
      setAlert(latest);
    }
  }, [latest?.receivedAt]);

  useEffect(() => {
    if (!alert) return;
    const t = setTimeout(() => setAlert(null), alert.event === 'TAMPER_ALERT' ? 10000 : 5000);
    return () => clearTimeout(t);
  }, [alert]);

  useEffect(() => {
    apiClient.get('/cases').then(res => {
      setMyCases(res.data.filter((c: any) => c.user_is_assigned));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const isPublicGuide = location.pathname === '/guide';

  if (!user && !isPublicGuide) return null;
  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="bg-slate-900 text-white px-4 py-3 flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-cyan-400" />
          <span className="font-semibold tracking-wide">LEXSECURE</span>
          <span className="text-xs text-slate-400">Guide</span>
          <Link to="/login" className="ml-auto text-xs text-cyan-400 hover:text-cyan-300">
            Sign in →
          </Link>
        </div>
        <main className="p-4 sm:p-6 max-w-5xl mx-auto">
          <Outlet />
        </main>
      </div>
    );
  }

  const closeSidebar = () => setSidebarOpen(false);

  const sidebar = (
    <div className="w-64 bg-ncrb-navy text-white flex flex-col h-full">
      <div className="p-4 flex items-center space-x-3 border-b border-slate-700">
        <ShieldCheck className="w-8 h-8 text-cyan-400 flex-shrink-0" />
        <div>
          <h1 className="font-bold text-xl tracking-wider">LEXSECURE</h1>
          <p className="text-xs text-slate-400">NCRB • Cyber Division</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4" aria-label="Main navigation">
        <ul className="space-y-1">
          <NavItem to="/dashboard" icon={<Activity />} label="Dashboard" onClick={closeSidebar} />
          <NavItem to="/cases" icon={<FolderOpen />} label="Cases" onClick={closeSidebar} />
          <NavItem to="/documents" icon={<FileText />} label="Documents" onClick={closeSidebar} />
          <NavItem to="/search" icon={<Search />} label="AI Search" onClick={closeSidebar} />
          <NavItem to="/assistant" icon={<Users />} label="AI Assistant" onClick={closeSidebar} />
          <NavItem to="/integrity" icon={<FileSignature />} label="Integrity Ledger" onClick={closeSidebar} />
          <NavItem to="/audit" icon={<AlertTriangle />} label="Audit Trail" onClick={closeSidebar} />
          {(user.role === 'ADMINISTRATOR' || user.role === 'SUPERVISOR') && (
            <NavItem to="/admin" icon={<ShieldAlert />} label="Administration" onClick={closeSidebar} />
          )}
          {(user.role === 'ADMINISTRATOR' || user.role === 'SUPERVISOR') && (
            <NavItem to="/leak" icon={<Fingerprint />} label="Leak Investigator" onClick={closeSidebar} />
          )}
          <NavItem to="/guide" icon={<BookOpen />} label="Guide" onClick={closeSidebar} />
        </ul>
      </nav>

      <div className="p-4 border-t border-slate-700 bg-slate-800/60">
        <div className="flex items-center gap-3 bg-slate-800 border border-slate-700 rounded-xl p-3">
          <div className="h-10 w-10 rounded-full bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 flex items-center justify-center font-bold text-lg flex-shrink-0">
            {user.full_name.charAt(0)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-white text-sm truncate">{user.full_name}</p>
            <p className="mt-1 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-400/30 tracking-wide">
                {user.role}
              </span>
              {mfaVerified && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-400/30 tracking-wide">
                  MFA ✓
                </span>
              )}
            </p>
            <p className="text-[11px] text-slate-400 truncate mt-1">{user.department}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-400/40 text-red-300 hover:bg-red-500/25 hover:text-red-200 text-sm font-semibold transition-colors"
        >
          <LogOut className="w-4 h-4" /> Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="hidden md:block h-full">{sidebar}</aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={closeSidebar} aria-hidden="true" />
          <aside className="absolute left-0 top-0 bottom-0 z-50 h-full shadow-2xl">
            <button
              onClick={closeSidebar}
              aria-label="Close menu"
              className="absolute top-4 right-3 text-slate-400 hover:text-white z-10"
            >
              <X className="w-5 h-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-4 sm:px-6 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
              className="md:hidden p-2 -ml-2 text-slate-600 hover:bg-slate-100 rounded-lg"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="font-medium text-slate-600 capitalize">
              {location.pathname.split('/')[1] || 'Dashboard'}
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <span
              className={`hidden sm:flex items-center text-xs font-medium px-3 py-1 rounded-full border ${connected ? 'bg-red-50 text-red-600 border-red-200' : 'bg-slate-100 text-slate-400 border-slate-200'}`}
              title={connected ? 'Connected to the live security event stream' : 'Live security feed reconnecting…'}
            >
              <Radio className={`w-3.5 h-3.5 mr-1.5 ${connected ? 'text-red-500 animate-pulse' : ''}`} />
              {connected ? 'LIVE FEED' : 'FEED OFFLINE'}
            </span>
            {mfaVerified && (
              <span className="hidden sm:flex items-center text-xs font-medium bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full border border-emerald-200">
                <ShieldCheck className="w-4 h-4 mr-1" />
                MFA VERIFIED
              </span>
            )}
            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setProfileOpen(v => !v)}
                aria-label="Open profile menu"
                aria-expanded={profileOpen}
                className="h-9 w-9 bg-indigo-100 text-indigo-700 rounded-full flex items-center justify-center font-bold flex-shrink-0 hover:bg-indigo-200 hover:ring-2 hover:ring-indigo-300 transition-all"
                title={`${user.full_name} — view profile`}
              >
                {user.full_name.charAt(0)}
              </button>

              {profileOpen && (
                <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden z-50">
                  <div className="bg-slate-900 text-white p-4">
                    <div className="flex items-center gap-3">
                      <div className="h-11 w-11 bg-indigo-500 rounded-full flex items-center justify-center font-bold text-lg flex-shrink-0">
                        {user.full_name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold truncate">{user.full_name}</p>
                        <p className="text-xs text-slate-300 flex items-center gap-1">
                          <BadgeCheck className="w-3.5 h-3.5 text-cyan-400" /> {user.role}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="p-4 space-y-2.5 text-sm">
                    <ProfileRow icon={<Mail className="w-4 h-4" />} label="Email" value={user.email} />
                    <ProfileRow icon={<Building2 className="w-4 h-4" />} label="Department" value={user.department} />
                    <ProfileRow icon={<ShieldCheck className="w-4 h-4" />} label="Badge No." value={user.badge_number || '—'} />
                    <ProfileRow
                      icon={<KeyRound className="w-4 h-4" />}
                      label="MFA"
                      value={mfaVerified ? 'Verified this session' : (user.mfa_enabled ? 'Enabled' : 'Disabled')}
                    />
                    <div className="pt-2 border-t border-slate-100">
                      <p className="text-xs font-bold text-slate-500 uppercase mb-1.5">
                        Assigned Cases ({myCases.length})
                      </p>
                      {myCases.length === 0 && <p className="text-xs text-slate-400">No case assignments.</p>}
                      <div className="space-y-1 max-h-32 overflow-y-auto">
                        {myCases.slice(0, 6).map((c: any) => (
                          <p key={c.id} className="text-xs text-slate-600 font-mono truncate" title={c.title}>
                            {c.id}
                          </p>
                        ))}
                      </div>
                    </div>
                    <button
                      onClick={logout}
                      className="w-full mt-1 flex items-center justify-center gap-2 px-3 py-2 bg-slate-100 hover:bg-red-50 text-slate-700 hover:text-red-700 text-sm font-medium rounded-lg transition-colors"
                    >
                      <LogOut className="w-4 h-4" /> Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-slate-50">
          {backendDown && (
            <div role="alert" className="mb-4 flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 px-4 py-3">
              <WifiOff className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-red-800">
                  Backend API unreachable — case data cannot load
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-red-700">
                  Nothing has been deleted: the interface is showing empty lists because the API at{' '}
                  <code className="rounded bg-white/70 px-1 py-0.5 font-mono">{API_URL}</code> is offline.
                  Start it with <code className="rounded bg-white/70 px-1 py-0.5 font-mono">./start.sh</code>,
                  then retry.
                </p>
              </div>
              <button
                onClick={handleRecheck}
                disabled={rechecking}
                className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100 disabled:opacity-60"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${rechecking ? 'animate-spin' : ''}`} />
                {rechecking ? 'Checking…' : 'Retry'}
              </button>
            </div>
          )}
          <Outlet />
        </main>
      </div>

      {alert && (
        <div className="fixed top-20 right-4 z-[60] max-w-sm w-[calc(100%-2rem)] sm:w-auto">
          <div className={`rounded-xl shadow-2xl border-2 p-4 backdrop-blur ${
            alert.event === 'TAMPER_ALERT'
              ? 'bg-red-50 border-red-400 animate-pulse'
              : 'bg-emerald-50 border-emerald-400'
          }`}>
            <div className="flex items-start gap-3">
              {alert.event === 'TAMPER_ALERT' ? (
                <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0 animate-bounce" />
              ) : (
                <ShieldCheck className="w-6 h-6 text-emerald-600 flex-shrink-0" />
              )}
              <div className="min-w-0">
                <p className={`font-bold text-sm ${alert.event === 'TAMPER_ALERT' ? 'text-red-700' : 'text-emerald-700'}`}>
                  {alert.event === 'TAMPER_ALERT' ? '⚠ TAMPERING DETECTED' : '✓ INTEGRITY RESTORED'}
                </p>
                <p className="text-xs text-slate-600 mt-1">{alert.data?.message}</p>
                <button
                  onClick={() => { setAlert(null); navigate('/integrity'); }}
                  className={`mt-2 text-xs font-semibold underline ${alert.event === 'TAMPER_ALERT' ? 'text-red-700' : 'text-emerald-700'}`}
                >
                  View live ledger →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ProfileRow = ({ icon, label, value }: { icon: React.ReactNode, label: string, value: string }) => (
  <div className="flex items-center gap-2.5">
    <span className="text-slate-400 flex-shrink-0">{icon}</span>
    <span className="text-slate-500 text-xs w-20 flex-shrink-0">{label}</span>
    <span className="font-medium text-slate-800 text-xs truncate">{value}</span>
  </div>
);

const NavItem = ({ to, icon, label, onClick }: { to: string, icon: React.ReactNode, label: string, onClick?: () => void }) => {
  return (
    <li>
      <NavLink
        to={to}
        onClick={onClick}
        className={({ isActive }) =>
          `flex items-center px-4 py-2.5 text-sm transition-colors ${
            isActive
              ? 'bg-slate-800 text-cyan-400 border-l-4 border-cyan-400'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white border-l-4 border-transparent'
          }`
        }
      >
        <span className="w-5 h-5 mr-3 flex-shrink-0">{icon}</span>
        {label}
      </NavLink>
    </li>
  );
};
