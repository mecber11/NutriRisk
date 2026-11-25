import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import {
  Badge,
  Card,
  Empty,
  ErrorBox,
  PageHeader,
  dateTime,
} from '../components/ui';
import type {
  AgentAnswer,
  AgentCapability,
  AgentMessage,
  AgentSessionDetail,
  ChatSession,
} from '../types';

interface Bubble {
  key: string;
  role: 'user' | 'assistant';
  content: string;
  meta?: Record<string, unknown>;
}

const FALLBACK_SUGGESTIONS = [
  '¿Cuál es la prevalencia de retraso en el crecimiento en 2023?',
  '¿Qué territorios priorizar en la región Norte?',
  'Compara la prevalencia por sexo',
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo contactar al agente.';
}

function toolsOf(meta?: Record<string, unknown>): string[] {
  const value = meta?.tools_used;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string');
}

function intentOf(meta?: Record<string, unknown>): string | null {
  const value = meta?.intent;
  return typeof value === 'string' ? value : null;
}

export default function Agent() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Bubble[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[] | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const capabilitiesQuery = useQuery({
    queryKey: ['agent', 'capabilities'],
    queryFn: () => api.get<AgentCapability[]>('/agent/capabilities'),
  });

  const sessionsQuery = useQuery({
    queryKey: ['agent', 'sessions'],
    queryFn: () => api.get<ChatSession[]>('/agent/sessions'),
  });

  const capabilities = capabilitiesQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];
  const activeSession = sessions.find((session) => session.id === sessionId);

  const initialSuggestions = useMemo(() => {
    const fromCapabilities = capabilities
      .flatMap((capability) => capability.examples.slice(0, 1))
      .slice(0, 4);
    return fromCapabilities.length > 0 ? fromCapabilities : FALLBACK_SUGGESTIONS;
  }, [capabilities]);

  const visibleSuggestions = suggestions ?? initialSuggestions;

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  async function sendMessage(text?: string) {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    setInput('');
    setError(null);
    setSuggestions(null);
    const userBubble: Bubble = {
      key: `user-${Date.now()}`,
      role: 'user',
      content,
    };
    setMessages((current) => [...current, userBubble]);
    setSending(true);
    try {
      const answer = await api.post<AgentAnswer>('/agent/chat', {
        message: content,
        session_id: sessionId ?? undefined,
      });
      setSessionId(answer.session_id);
      setMessages((current) => [
        ...current,
        {
          key: `assistant-${answer.session_id}-${current.length}`,
          role: 'assistant',
          content: answer.answer,
          meta: { intent: answer.intent, tools_used: answer.tools_used },
        },
      ]);
      setSuggestions(answer.suggestions.length ? answer.suggestions : null);
      void queryClient.invalidateQueries({ queryKey: ['agent', 'sessions'] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage();
  }

  function newConversation() {
    setSessionId(null);
    setMessages([]);
    setSuggestions(null);
    setError(null);
    setInput('');
  }

  async function openSession(id: number) {
    setError(null);
    setLoadingSession(true);
    try {
      const detail = await api.get<AgentSessionDetail>(`/agent/sessions/${id}`);
      setSessionId(detail.id);
      setMessages(
        detail.messages.map((message: AgentMessage) => ({
          key: `server-${message.id}`,
          role: message.role === 'user' ? 'user' : 'assistant',
          content: message.content,
          meta: message.meta ?? undefined,
        })),
      );
      setSuggestions(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingSession(false);
    }
  }

  async function removeSession(id: number) {
    if (!window.confirm('¿Eliminar esta conversación?')) return;
    try {
      await api.del<unknown>(`/agent/sessions/${id}`);
      if (id === sessionId) newConversation();
      void queryClient.invalidateQueries({ queryKey: ['agent', 'sessions'] });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Agente analista"
        subtitle="Consulte indicadores, prioridades y explicaciones en lenguaje natural. El agente usa herramientas auditables del sistema."
        actions={<Badge tone="brand">Agente determinista</Badge>}
      />

      <div className="agent-layout">
        <Card
          title="Conversaciones"
          subtitle={`${sessions.length} sesiones`}
          actions={
            <button type="button" className="btn btn-sm btn-primary" onClick={newConversation}>
              Nueva
            </button>
          }
        >
          {sessionsQuery.isError && <ErrorBox message={errorMessage(sessionsQuery.error)} />}
          {sessionsQuery.isLoading && <small>Cargando historial…</small>}
          {sessions.length === 0 && !sessionsQuery.isLoading && (
            <Empty title="Sin conversaciones" hint="Inicie una consulta para crear la primera sesión." />
          )}
          <div className="session-list">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${session.id === sessionId ? 'active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => void openSession(session.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    void openSession(session.id);
                  }
                }}
              >
                <span className="title" title={session.title}>
                  {session.title}
                </span>
                <button
                  type="button"
                  className="session-delete"
                  title="Eliminar conversación"
                  onClick={(event) => {
                    event.stopPropagation();
                    void removeSession(session.id);
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <div style={{ marginTop: '0.8rem', fontSize: '0.72rem', color: 'var(--muted)' }}>
            Las respuestas se basan en datos sintéticos y quedan auditadas.
          </div>
        </Card>

        <Card
          title={activeSession ? activeSession.title : 'Nueva conversación'}
          subtitle={
            activeSession
              ? `Actualizada ${dateTime(activeSession.updated_at)}`
              : 'Escriba su pregunta y presione Enter para enviar.'
          }
          actions={
            <Badge tone={sending ? 'warning' : 'info'}>
              {sending ? 'Analizando…' : `${messages.length} mensajes`}
            </Badge>
          }
        >
          <div className="chat">
            <div className="chat-log" ref={logRef}>
              {messages.length === 0 && !loadingSession && (
                <div style={{ padding: '1rem 0' }}>
                  <div className="bubble assistant" style={{ maxWidth: '100%' }}>
                    <strong>Hola, soy el agente analista de NutriRisk AI.</strong>
                    <div style={{ marginTop: '0.35rem' }}>
                      Puedo resumir prevalencias, priorizar territorios, explicar el riesgo de un niño o
                      comparar grupos. Pruebe una de estas preguntas:
                    </div>
                    <div className="chip-row" style={{ marginTop: '0.55rem' }}>
                      {visibleSuggestions.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          className="chip"
                          onClick={() => void sendMessage(suggestion)}
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {loadingSession && (
                <div className="bubble assistant">
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />{' '}
                  Cargando conversación…
                </div>
              )}

              {messages.map((message) => (
                <div key={message.key} className={`bubble ${message.role}`}>
                  <div>{message.content}</div>
                  {message.role === 'assistant' && message.meta && (
                    <div className="chat-meta">
                      {intentOf(message.meta) && <Badge tone="info">Intención: {intentOf(message.meta)}</Badge>}
                      {toolsOf(message.meta).map((tool) => (
                        <Badge key={tool} tone="neutral">
                          Herramienta: {tool}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {sending && (
                <div className="bubble assistant">
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />{' '}
                  Consultando indicadores y preparando la respuesta…
                </div>
              )}
            </div>

            {messages.length > 0 && !sending && visibleSuggestions.length > 0 && (
              <div className="chip-row">
                {visibleSuggestions.slice(0, 4).map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="chip"
                    onClick={() => void sendMessage(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            {error && <ErrorBox message={error} />}

            <form className="chat-input" onSubmit={handleSubmit}>
              <input
                type="text"
                value={input}
                placeholder="Escriba su consulta y presione Enter…"
                onChange={(event) => setInput(event.target.value)}
                disabled={sending || loadingSession}
              />
              <button type="submit" className="btn btn-primary" disabled={sending || !input.trim()}>
                Enviar
              </button>
            </form>
            <small style={{ color: 'var(--muted)' }}>
              Enter envía el mensaje. El agente no emite diagnósticos clínicos.
            </small>
          </div>
        </Card>
      </div>

      <Card
        title="Capacidades del agente"
        subtitle="Intenciones reconocidas y ejemplos de consulta."
      >
        {capabilitiesQuery.isError && <ErrorBox message={errorMessage(capabilitiesQuery.error)} />}
        {capabilitiesQuery.isLoading && <small>Cargando capacidades…</small>}
        <div className="grid grid-2">
          {capabilities.map((capability) => (
            <div key={capability.intent}>
              <div style={{ fontWeight: 650, fontSize: '0.86rem' }}>{capability.intent}</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--muted)', lineHeight: 1.5 }}>
                {capability.description}
              </div>
              {capability.examples.length > 0 && (
                <div className="chip-row" style={{ marginTop: '0.35rem' }}>
                  {capability.examples.slice(0, 2).map((example) => (
                    <button
                      key={example}
                      type="button"
                      className="chip"
                      onClick={() => void sendMessage(example)}
                    >
                      {example}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}
