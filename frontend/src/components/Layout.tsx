import { useEffect, useRef } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { api, getSessionId } from '../api/client';
import { useAuth } from '../auth/AuthContext';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  module: string;
  group: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/', label: 'Predicción de desnutrición', icon: '∑', module: 'experiments', group: 'Predicción con datos reales' },
  { path: '/datasets', label: 'Dataset de desnutrición y factores', icon: '▦', module: 'experiments', group: 'Predicción con datos reales' },
  { path: '/demo', label: 'Tablero sintético histórico', icon: '◈', module: 'dashboard', group: 'Demo sintética separada' },
  { path: '/mapa', label: 'Mapa sintético histórico', icon: '◈', module: 'geo', group: 'Demo sintética separada' },
  { path: '/auditoria', label: 'Bitácora', icon: '☰', module: 'audit', group: 'Gobernanza' },
  { path: '/usuarios', label: 'Usuarios', icon: '☺', module: 'users', group: 'Gobernanza' },
];
const REAL_ROUTES = ['/', '/investigacion', '/datasets', '/modelos'];

function moduleForPath(path: string): string {
  const item = [...NAV_ITEMS].sort((a, b) => b.path.length - a.path.length).find((entry) =>
    entry.path === '/' ? path === '/' : path.startsWith(entry.path),
  );
  return item?.module ?? 'dashboard';
}

export default function Layout() {
  const { user, logout, can } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const previousModule = useRef<string | null>(null);
  const sessionId = getSessionId();

  useEffect(() => {
    const module = moduleForPath(location.pathname);
    if (previousModule.current && previousModule.current !== module) {
      void api
        .post('/audit/navigation', {
          module: previousModule.current,
          event_type: 'EXIT',
          path: location.pathname,
          session_id: sessionId,
        })
        .catch(() => undefined);
    }
    void api
      .post('/audit/navigation', {
        module,
        event_type: 'ENTER',
        path: location.pathname,
        session_id: sessionId,
      })
      .catch(() => undefined);
    previousModule.current = module;
  }, [location.pathname, sessionId]);

  useEffect(() => {
    const handler = () => {
      if (previousModule.current) {
        const payload = JSON.stringify({
          module: previousModule.current,
          event_type: 'EXIT',
          path: window.location.pathname,
          session_id: sessionId,
        });
        navigator.sendBeacon?.(
          '/api/v1/audit/navigation',
          new Blob([payload], { type: 'application/json' }),
        );
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [sessionId]);

  const visibleItems = NAV_ITEMS.filter((item) => can(item.module, 'read') || can(item.module, 'use'));
  const groups = Array.from(new Set(visibleItems.map((item) => item.group)));
  const initials = (user?.full_name ?? 'NR')
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">NR</div>
          <div>
            <div className="brand-name">NutriRisk AI</div>
            <div className="brand-sub">Predicción de desnutrición infantil</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {groups.map((group) => (
            <div key={group}>
              <div className="nav-group-label">{group}</div>
              {visibleItems
                .filter((item) => item.group === group)
                .map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) => `nav-link ${isActive || (item.path === '/' && ['/investigacion', '/modelos'].includes(location.pathname)) ? 'active' : ''}`}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span>{item.label}</span>
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div>Predicción de desnutrición · Datos reales JME / Banco Mundial</div>
          <div style={{ opacity: 0.7 }}>v1.0.0 · sesión {sessionId.slice(0, 8)}</div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-title">Observatorio de Nutrición Infantil</div>
          <span className="badge" data-tone="brand">{REAL_ROUTES.includes(location.pathname) ? 'Datos públicos reales' : 'Demo sintética / administración'}</span>
          <div className="topbar-spacer" />
          <div className="topbar-user">
            <div className="avatar">{initials}</div>
            <div>
              <div style={{ fontWeight: 600 }}>{user?.full_name}</div>
              <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{user?.role.name}</div>
            </div>
            <button
              type="button"
              className="btn btn-sm"
              onClick={async () => {
                await logout();
                navigate('/login', { replace: true });
              }}
            >
              Salir
            </button>
          </div>
        </header>
        <main className="page">
          {!REAL_ROUTES.includes(location.pathname) && !['/usuarios','/auditoria'].includes(location.pathname) && <div className="notice" style={{marginBottom:20}}>DEMO SINTÉTICA HISTÓRICA. Los registros individuales, mapas, modelos y métricas de este módulo no corresponden al estudio público real. No usar para conclusiones científicas o clínicas.</div>}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
