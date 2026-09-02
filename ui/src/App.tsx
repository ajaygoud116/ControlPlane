import { Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Run from './pages/Run';
import RunDetail from './pages/RunDetail';
import Activity from './pages/Activity';
import Effect from './pages/Effect';
import Policies from './pages/Policies';
import Audit from './pages/Audit';
import Insights from './pages/Insights';
import Settings from './pages/Settings';
import { api } from './api';

const NAV_PRIMARY = [
  { to: '/run', label: 'CONTROL ROOM', glyph: '01', description: 'AI execution workspace' },
  { to: '/activity', label: 'RUNS', glyph: '02', description: 'Execution history' },
  { to: '/effect', label: 'EFFECTS', glyph: '03', description: 'What ControlPlane changed' },
  { to: '/policies', label: 'POLICIES', glyph: '04', description: 'Governance rules' },
  { to: '/audit', label: 'AUDIT', glyph: '05', description: 'Decision evidence' },
];

function Sidebar() {
  const [health, setHealth] = useState<'checking' | 'operational' | 'offline'>('checking');

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      api.health().then(() => {
        if (!cancelled) setHealth('operational');
      }).catch(() => {
        if (!cancelled) setHealth('offline');
      });
    };
    check();
    const id = setInterval(check, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const statusText = health === 'operational' ? 'SYSTEM ONLINE' : health === 'offline' ? 'OFFLINE' : 'CHECKING';

  return (
    <aside className="w-sidebar h-full bg-white border-r border-cp-border flex flex-col shrink-0">
      {/* Product Identity */}
      <div className="px-5 pt-6 pb-5 border-b border-cp-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded bg-cp-brand flex items-center justify-center">
            <span className="text-white text-caption font-bold">CP</span>
          </div>
          <div>
            <div className="text-[13px] font-bold tracking-[0.06em] text-cp-text">CONTROLPLANE</div>
          </div>
        </div>
        <div className="text-caption text-cp-text-muted mt-2">AI Runtime Governance</div>
      </div>

      {/* Primary Navigation */}
      <nav className="flex-1 px-3 pt-4 space-y-0.5">
        {NAV_PRIMARY.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-150 group ${
                isActive
                  ? 'bg-cp-accent text-white'
                  : 'text-cp-text-secondary hover:text-cp-text hover:bg-cp-surface-2 border border-transparent'
              }`
            }
          >
            <span className={`text-[10px] font-mono w-5 text-center transition-colors ${
              'text-current opacity-50 group-hover:opacity-100'
            }`}>
              {item.glyph}
            </span>
            <span className="text-body-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Secondary Navigation */}
      <div className="px-3 pb-4 space-y-1">
        <div className="cp-divider mb-3" />

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-150 ${
              isActive
                ? 'bg-cp-accent text-white'
                : 'text-cp-text-secondary hover:text-cp-text hover:bg-cp-surface-2 border border-transparent'
            }`
          }
        >
          <span className="text-[10px] font-mono text-cp-text-muted w-5 text-center opacity-50">99</span>
          <span className="text-body-sm font-medium">SETTINGS</span>
        </NavLink>

        {/* System Status */}
        <div className="mt-4 px-3 py-2.5 rounded-md bg-cp-surface-2 border border-cp-border/50">
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${health === 'operational' ? 'bg-cp-allow animate-pulse-dot' : health === 'offline' ? 'bg-cp-block' : 'bg-cp-unknown'}`} />
            <span className="text-[10px] font-mono text-cp-text-muted tracking-wider">{statusText}</span>
          </div>
        </div>

        {/* Demo Environment Badge */}
        <div className="mt-2 px-3 py-2.5 rounded-md bg-cp-accent/8 border border-cp-accent/10">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-cp-accent" />
            <span className="text-[10px] font-medium text-cp-accent tracking-wider">DEMO ENVIRONMENT</span>
          </div>
          <p className="text-[10px] text-cp-text-muted mt-1.5 leading-relaxed">
            Deterministic Response Corpus
          </p>
        </div>
      </div>
    </aside>
  );
}

function PageWrapper({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return (
    <div key={location.pathname} className="cp-page-transition cp-page-visible">
      {children}
    </div>
  );
}

export default function App() {
  useEffect(() => {
    api.resetSession().catch(() => {});
  }, []);

  return (
    <div className="min-h-screen relative z-10 flex items-center justify-center p-6 lg:p-8">
      <div className="flex w-full h-[calc(100vh-3rem)] bg-cp-surface rounded-xl overflow-hidden shadow-ambient">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <PageWrapper>
            <Routes>
              <Route path="/" element={<Run />} />
              <Route path="/run" element={<Run />} />
              <Route path="/run/:id" element={<RunDetail />} />
              <Route path="/activity" element={<Activity />} />
              <Route path="/interactions/:id" element={<RunDetail />} />
              <Route path="/effect" element={<Effect />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </PageWrapper>
        </main>
      </div>
    </div>
  );
}
