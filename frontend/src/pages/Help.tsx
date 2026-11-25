import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import {
  Badge,
  Card,
  Empty,
  ErrorBox,
  Loading,
  PageHeader,
} from '../components/ui';
import type { HelpFaq, HelpSection } from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar la ayuda.';
}

export default function Help() {
  const sectionsQuery = useQuery({
    queryKey: ['help', 'sections'],
    queryFn: () => api.get<HelpSection[]>('/help'),
  });

  const faqQuery = useQuery({
    queryKey: ['help', 'faq'],
    queryFn: () => api.get<HelpFaq[]>('/help/faq'),
  });

  const sections = sectionsQuery.data ?? [];
  const faqs = faqQuery.data ?? [];

  return (
    <>
      <PageHeader
        title="Ayuda y documentación"
        subtitle="Guías de uso, conceptos metodológicos y preguntas frecuentes del observatorio."
        actions={<Badge tone="brand">Referencia OMS 2006</Badge>}
      />

      {sectionsQuery.isError && <ErrorBox message={errorMessage(sectionsQuery.error)} />}
      {sectionsQuery.isLoading && <Loading label="Cargando secciones de ayuda…" />}

      {sections.length === 0 && !sectionsQuery.isLoading && (
        <Empty title="Sin contenido de ayuda" hint="El servicio de ayuda no reporta secciones." />
      )}

      <div className="grid grid-2">
        {sections.map((section) => (
          <Card key={section.code} title={section.title} subtitle={`Sección ${section.code}`}>
            <div className="help-list">
              {section.content.map((paragraph) => (
                <p key={paragraph} style={{ fontSize: '0.84rem', margin: 0 }}>
                  {paragraph}
                </p>
              ))}
            </div>
            {section.links.length > 0 && (
              <div style={{ marginTop: '0.7rem' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: '0.25rem' }}>
                  Enlaces
                </div>
                <div className="chip-row">
                  {section.links.map((link) => (
                    <a
                      key={link.href}
                      className="chip"
                      href={link.href}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>

      <Card
        title="Preguntas frecuentes"
        subtitle="Haga clic en una pregunta para desplegar la respuesta."
        actions={<Badge tone="info">{faqs.length} preguntas</Badge>}
      >
        {faqQuery.isError && <ErrorBox message={errorMessage(faqQuery.error)} />}
        {faqQuery.isLoading && <Loading label="Cargando preguntas frecuentes…" />}
        {!faqQuery.isLoading && faqs.length === 0 && <Empty title="Sin preguntas registradas" />}
        {faqs.map((faq) => (
          <details key={faq.question} className="faq-item">
            <summary>{faq.question}</summary>
            <p>{faq.answer}</p>
          </details>
        ))}
      </Card>
    </>
  );
}
