import { Link } from 'react-router-dom';
import { Card, PageHeader } from '../components/ui';

export default function NotFound() {
  return (
    <>
      <PageHeader
        title="Página no encontrada"
        subtitle="La dirección solicitada no existe o fue movida."
      />
      <Card>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: '0.7rem',
            padding: '2.5rem 1rem',
          }}
        >
          <div style={{ fontSize: '3.4rem', fontWeight: 800, color: 'var(--brand)', lineHeight: 1 }}>
            404
          </div>
          <h2>No pudimos encontrar esta sección</h2>
          <p style={{ color: 'var(--muted)', maxWidth: 460, margin: 0 }}>
            Verifique la dirección o regrese al tablero para continuar explorando los indicadores
            nutricionales.
          </p>
          <Link className="btn btn-primary" to="/" style={{ marginTop: '0.6rem' }}>
            Volver al tablero
          </Link>
        </div>
      </Card>
    </>
  );
}
