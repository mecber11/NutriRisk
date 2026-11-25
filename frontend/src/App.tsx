import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { useAuth } from './auth/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import RiskMapPage from './pages/RiskMap';
import Territories from './pages/Territories';
import TerritoryDetail from './pages/TerritoryDetail';
import Indicators from './pages/Indicators';
import Models from './pages/Models';
import Explainability from './pages/Explainability';
import Fairness from './pages/Fairness';
import Datasets from './pages/Datasets';
import Reports from './pages/Reports';
import Audit from './pages/Audit';
import Agent from './pages/Agent';
import Users from './pages/Users';
import Settings from './pages/Settings';
import Help from './pages/Help';
import NotFound from './pages/NotFound';
import Alerts from './pages/Alerts';
import Research from './pages/Research';

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="state" style={{ margin: '3rem' }}>
        <div className="spinner" />
        <span>Cargando sesión…</span>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Research />} />
        <Route path="/demo" element={<Dashboard />} />
        <Route path="/mapa" element={<RiskMapPage />} />
        <Route path="/territorios" element={<Territories />} />
        <Route path="/territorios/:code" element={<TerritoryDetail />} />
        <Route path="/indicadores" element={<Indicators />} />
        <Route path="/modelos" element={<Research />} />
        <Route path="/explicabilidad" element={<Explainability />} />
        <Route path="/equidad" element={<Fairness />} />
        <Route path="/datasets" element={<Research />} />
        <Route path="/reportes" element={<Reports />} />
        <Route path="/alertas" element={<Alerts />} />
        <Route path="/investigacion" element={<Research />} />
        <Route path="/auditoria" element={<Audit />} />
        <Route path="/agente" element={<Agent />} />
        <Route path="/usuarios" element={<Users />} />
        <Route path="/configuracion" element={<Settings />} />
        <Route path="/ayuda" element={<Help />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
