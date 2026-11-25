import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Field } from '../components/ui';

interface ForgotResponse {
  message: string;
  reset_token?: string | null;
  expires_in_minutes?: number;
}

const DEMO_CREDENTIALS = [
  { role: 'Administrador', email: 'admin@nutririsk.ai', password: 'Admin#2026!' },
  { role: 'Científico de datos', email: 'cientifico@nutririsk.ai', password: 'Ciencia#2026!' },
  { role: 'Analista de salud', email: 'analista@nutririsk.ai', password: 'Analista#2026!' },
  { role: 'Gestor', email: 'gestor@nutririsk.ai', password: 'Gestor#2026!' },
  { role: 'Auditor', email: 'auditor@nutririsk.ai', password: 'Auditor#2026!' },
];

type Mode = 'login' | 'forgot' | 'reset';

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [tokenPreview, setTokenPreview] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  function useCredential(credential: (typeof DEMO_CREDENTIALS)[number]) {
    setEmail(credential.email);
    setPassword(credential.password);
    setError(null);
    setInfo(`Credenciales de ${credential.role} cargadas. Presione «Ingresar».`);
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    if (!email.trim() || !password) {
      setError('Ingrese su correo institucional y su contraseña.');
      return;
    }
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo iniciar sesión.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleForgot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    if (!forgotEmail.trim()) {
      setError('Ingrese el correo asociado a su cuenta.');
      return;
    }
    setSubmitting(true);
    try {
      const response = await api.post<ForgotResponse>('/auth/forgot-password', {
        email: forgotEmail.trim(),
      });
      setInfo(response.message);
      setResetToken(response.reset_token ?? '');
      setTokenPreview(response.reset_token ?? null);
      setMode('reset');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo solicitar el restablecimiento.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    if (!resetToken.trim()) {
      setError('Ingrese el token de restablecimiento.');
      return;
    }
    if (newPassword.length < 10) {
      setError('La contraseña debe tener al menos 10 caracteres.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setSubmitting(true);
    try {
      const response = await api.post<{ message?: string }>('/auth/reset-password', {
        token: resetToken.trim(),
        new_password: newPassword,
      });
      setInfo(response.message ?? 'Contraseña actualizada. Ya puede iniciar sesión.');
      setEmail(forgotEmail.trim());
      setPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setResetToken('');
      setTokenPreview(null);
      setMode('login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo restablecer la contraseña.');
    } finally {
      setSubmitting(false);
    }
  }

  function backToLogin() {
    setMode('login');
    setError(null);
    setInfo(null);
  }

  return (
    <div className="login-shell">
      <aside className="login-aside">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
          <div className="brand-mark" style={{ width: 44, height: 44, fontSize: '1.15rem' }}>
            NR
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.15rem', color: '#fff' }}>NutriRisk AI</div>
            <div style={{ fontSize: '0.7rem', letterSpacing: '0.12em', color: '#7dd3c8' }}>
              OBSERVATORIO NUTRICIONAL
            </div>
          </div>
        </div>

        <h1>Investigación nutricional con datos públicos reales</h1>
        <p>Prevalencia nacional de retraso del crecimiento publicada por JME y Banco Mundial. Evaluación geográfica de cinco modelos con evidencia reproducible.</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', fontSize: '0.86rem' }}>
          <div>✓ 161 países y siete regiones</div>
          <div>✓ 350 candidatos y 35 ajustes finales</div>
          <div>✓ Pruebas estadísticas, hiperparámetros e intervalos</div>
          <div>✓ Datos, predicciones, curvas y figuras descargables</div>
        </div>
        <div style={{ marginTop: '1rem', fontSize: '0.74rem', color: '#7dd3c8' }}>
          Estudio ecológico nacional · sin validación clínica individual. Demo sintética histórica separada.
        </div>
      </aside>

      <div className="login-card-wrap">
        <div className="login-card">
          {mode === 'login' && (
            <>
              <h2 style={{ fontSize: '1.3rem' }}>Iniciar sesión</h2>
              <p className="login-note" style={{ marginTop: '0.35rem' }}>
                Acceda con las credenciales institucionales asignadas a su rol.
              </p>

              {error && (
                <div className="error-box" style={{ marginTop: '0.8rem' }}>
                  {error}
                </div>
              )}
              {info && (
                <div className="notice" data-tone="ok" style={{ marginTop: '0.8rem' }}>
                  {info}
                </div>
              )}

              <form onSubmit={handleLogin} style={{ display: 'grid', gap: '0.7rem', marginTop: '0.8rem' }}>
                <Field label="Correo institucional">
                  <input
                    type="email"
                    value={email}
                    autoComplete="username"
                    placeholder="usuario@nutririsk.ai"
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </Field>
                <Field label="Contraseña">
                  <input
                    type="password"
                    value={password}
                    autoComplete="current-password"
                    placeholder="••••••••••"
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </Field>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Verificando…' : 'Ingresar'}
                </button>
              </form>

              <div style={{ marginTop: '0.55rem', textAlign: 'right' }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setForgotEmail(email || 'admin@nutririsk.ai');
                    setError(null);
                    setInfo(null);
                    setMode('forgot');
                  }}
                >
                  ¿Olvidó su contraseña?
                </button>
              </div>

              <div className="login-credentials">
                <div className="login-credentials-label">Credenciales de demostración</div>
                {DEMO_CREDENTIALS.map((credential) => (
                  <div
                    key={credential.email}
                    className="credential-chip"
                    role="button"
                    tabIndex={0}
                    title={`Usar la cuenta ${credential.role}`}
                    onClick={() => useCredential(credential)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        useCredential(credential);
                      }
                    }}
                  >
                    <span style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                      <span className="role">{credential.role}</span>
                      <span className="email">
                        {credential.email} · {credential.password}
                      </span>
                    </span>
                    <span className="badge" data-tone="brand">
                      Usar
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          {mode === 'forgot' && (
            <>
              <h2 style={{ fontSize: '1.3rem' }}>Recuperar acceso</h2>
              <p className="login-note" style={{ marginTop: '0.35rem' }}>
                Enviaremos un token temporal al correo registrado. En este entorno de demostración el
                token se muestra directamente en pantalla.
              </p>

              {error && (
                <div className="error-box" style={{ marginTop: '0.8rem' }}>
                  {error}
                </div>
              )}

              <form onSubmit={handleForgot} style={{ display: 'grid', gap: '0.7rem', marginTop: '0.8rem' }}>
                <Field label="Correo institucional">
                  <input
                    type="email"
                    value={forgotEmail}
                    autoComplete="username"
                    placeholder="usuario@nutririsk.ai"
                    onChange={(event) => setForgotEmail(event.target.value)}
                  />
                </Field>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Enviando…' : 'Enviar instrucciones'}
                </button>
              </form>

              <div style={{ marginTop: '0.6rem' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={backToLogin}>
                  ← Volver al inicio de sesión
                </button>
              </div>
            </>
          )}

          {mode === 'reset' && (
            <>
              <h2 style={{ fontSize: '1.3rem' }}>Nueva contraseña</h2>
              <p className="login-note" style={{ marginTop: '0.35rem' }}>
                {info ?? 'Introduzca el token recibido y defina una contraseña segura.'}
              </p>

              {tokenPreview && (
                <div className="notice" data-tone="info" style={{ marginTop: '0.7rem' }}>
                  <span>
                    <strong>Token de demostración:</strong>{' '}
                    <span className="mono" style={{ wordBreak: 'break-all' }}>
                      {tokenPreview}
                    </span>
                  </span>
                </div>
              )}
              {error && (
                <div className="error-box" style={{ marginTop: '0.7rem' }}>
                  {error}
                </div>
              )}

              <form onSubmit={handleReset} style={{ display: 'grid', gap: '0.7rem', marginTop: '0.8rem' }}>
                <Field label="Token de restablecimiento">
                  <input
                    type="text"
                    value={resetToken}
                    className="mono"
                    placeholder="Token recibido"
                    onChange={(event) => setResetToken(event.target.value)}
                  />
                </Field>
                <Field label="Nueva contraseña">
                  <input
                    type="password"
                    value={newPassword}
                    autoComplete="new-password"
                    placeholder="Mínimo 10 caracteres"
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </Field>
                <Field label="Confirmar contraseña">
                  <input
                    type="password"
                    value={confirmPassword}
                    autoComplete="new-password"
                    placeholder="Repita la contraseña"
                    onChange={(event) => setConfirmPassword(event.target.value)}
                  />
                </Field>
                <small style={{ color: 'var(--muted)' }}>
                  Debe incluir mayúscula, minúscula, dígito y símbolo.
                </small>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Actualizando…' : 'Actualizar contraseña'}
                </button>
              </form>

              <div style={{ marginTop: '0.6rem' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={backToLogin}>
                  ← Volver al inicio de sesión
                </button>
              </div>
            </>
          )}

          <p className="login-note">
            Al ingresar acepta que sus consultas queden registradas en la bitácora de auditoría del
            sistema.
          </p>
        </div>
      </div>
    </div>
  );
}
