import { Interpretation } from '../components/Interpretation';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  Badge,
  Card,
  DataTable,
  Empty,
  ErrorBox,
  Field,
  Loading,
  PageHeader,
  dateTime,
  num,
} from '../components/ui';
import type { Column } from '../components/ui';
import type { Page, RoleInfo, User, UserPermissions } from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.';
}

function passwordProblem(value: string): string | null {
  if (value.length < 10) return 'La contraseña debe tener al menos 10 caracteres.';
  if (!/[a-z]/.test(value)) return 'La contraseña debe incluir una minúscula.';
  if (!/[A-Z]/.test(value)) return 'La contraseña debe incluir una mayúscula.';
  if (!/[0-9]/.test(value)) return 'La contraseña debe incluir un dígito.';
  if (!/[^A-Za-z0-9]/.test(value)) return 'La contraseña debe incluir un símbolo.';
  return null;
}

function roleTone(code: string): 'brand' | 'info' | 'warning' | 'ok' | 'neutral' {
  switch (code) {
    case 'ADMIN':
      return 'brand';
    case 'DATA_SCIENTIST':
      return 'info';
    case 'PUBLIC_HEALTH_ANALYST':
      return 'ok';
    case 'MANAGER':
      return 'warning';
    default:
      return 'neutral';
  }
}

export default function Users() {
  const { user } = useAuth();
  if (user?.role.code !== 'ADMIN') {
    return (
      <>
        <PageHeader title="Usuarios y permisos" />
        <Empty
          title="No autorizado"
          hint="Esta sección está reservada a administradores del sistema."
        />
      </>
    );
  }
  return <UsersAdmin currentUserId={user.id} />;
}

function UsersAdmin({ currentUserId }: { currentUserId: number }) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [selected, setSelected] = useState<User | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [newRole, setNewRole] = useState('MANAGER');
  const [organization, setOrganization] = useState('');
  const [position, setPosition] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [newPassword, setNewPassword] = useState('');

  const usersQuery = useQuery({
    queryKey: ['users', 'list', page, appliedSearch, roleFilter],
    queryFn: () =>
      api.get<Page<User>>('/users', {
        page,
        page_size: 10,
        search: appliedSearch || undefined,
        role_code: roleFilter || undefined,
      }),
  });

  const rolesQuery = useQuery({
    queryKey: ['users', 'roles'],
    queryFn: () => api.get<RoleInfo[]>('/users/roles'),
  });

  const permissionsQuery = useQuery({
    queryKey: ['users', 'permissions'],
    queryFn: () => api.get<UserPermissions>('/users/permissions'),
  });

  const users = usersQuery.data?.items ?? [];
  const roles = rolesQuery.data ?? [];
  const permissions = permissionsQuery.data;

  useEffect(() => {
    if (selected) {
      setFullName(selected.full_name);
      setNewRole(selected.role.code);
      setOrganization(selected.organization ?? '');
      setPosition(selected.position ?? '');
      setIsActive(selected.is_active);
      setNewPassword('');
      setFormError(null);
    }
  }, [selected]);

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<User>('/users', {
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        role_code: newRole,
        organization: organization.trim() || null,
        position: position.trim() || null,
      }),
    onSuccess: (created) => {
      setMessage(`Usuario ${created.full_name} creado correctamente.`);
      setFormError(null);
      setEmail('');
      setFullName('');
      setPassword('');
      setOrganization('');
      setPosition('');
      setNewRole('MANAGER');
      void queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error('Seleccione un usuario.');
      return api.patch<User>(`/users/${selected.id}`, {
        full_name: fullName.trim(),
        role_code: newRole,
        is_active: isActive,
        organization: organization.trim() || null,
        position: position.trim() || null,
      });
    },
    onSuccess: (updated) => {
      setMessage(`Usuario ${updated.full_name} actualizado.`);
      setFormError(null);
      setSelected(updated);
      void queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  const resetMutation = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error('Seleccione un usuario.');
      return api.post<{ message?: string }>(`/users/${selected.id}/reset-password`, {
        new_password: newPassword,
      });
    },
    onSuccess: (result) => {
      setMessage(result.message ?? 'Contraseña restablecida.');
      setFormError(null);
      setNewPassword('');
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del<unknown>(`/users/${id}`),
    onSuccess: () => {
      setMessage('Usuario eliminado.');
      setFormError(null);
      setSelected(null);
      void queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setFormError(null);
    if (!email.trim() || !fullName.trim() || !password) {
      setFormError('Correo, nombre completo y contraseña son obligatorios.');
      return;
    }
    const problem = passwordProblem(password);
    if (problem) {
      setFormError(problem);
      return;
    }
    createMutation.mutate();
  }

  function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setFormError(null);
    if (!selected) return;
    if (!fullName.trim()) {
      setFormError('El nombre completo es obligatorio.');
      return;
    }
    updateMutation.mutate();
  }

  function handleReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setFormError(null);
    if (!selected) return;
    const problem = passwordProblem(newPassword);
    if (problem) {
      setFormError(problem);
      return;
    }
    resetMutation.mutate();
  }

  const columns: Column<User>[] = [
    {
      key: 'full_name',
      header: 'Usuario',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.full_name}</div>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{row.email}</div>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Rol',
      render: (row) => <Badge tone={roleTone(row.role.code)}>{row.role.name}</Badge>,
    },
    { key: 'organization', header: 'Organización', render: (row) => row.organization ?? '—' },
    { key: 'position', header: 'Cargo', render: (row) => row.position ?? '—' },
    {
      key: 'status',
      header: 'Estado',
      render: (row) => (
        <Badge tone={row.is_active ? 'ok' : 'danger'}>{row.is_active ? 'Activo' : 'Inactivo'}</Badge>
      ),
    },
    { key: 'last_login', header: 'Último acceso', render: (row) => dateTime(row.last_login_at) },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <div style={{ display: 'flex', gap: '0.3rem', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-sm" onClick={() => setSelected(row)}>
            Editar
          </button>
          {row.id !== currentUserId && (
            <button
              type="button"
              className="btn btn-sm btn-danger"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (window.confirm(`¿Eliminar al usuario ${row.full_name}?`)) {
                  deleteMutation.mutate(row.id);
                }
              }}
            >
              Eliminar
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Usuarios y permisos"
        subtitle="Administre cuentas, roles y el acceso por módulo del observatorio."
        actions={<Badge tone="brand">{num(usersQuery.data?.total ?? 0)} usuarios</Badge>}
      />

      {message && (
        <div className="notice" data-tone="ok">
          {message}
        </div>
      )}
      {formError && <ErrorBox message={formError} />}
      {usersQuery.isError && <ErrorBox message={errorMessage(usersQuery.error)} />}
      {rolesQuery.isError && <ErrorBox message={errorMessage(rolesQuery.error)} />}

      <div className="grid grid-sidebar">
        <div>
          <Card title="Cuentas registradas" subtitle="Filtre por nombre, correo o rol.">
            <form
              className="filters"
              style={{ marginBottom: '0.8rem' }}
              onSubmit={(event) => {
                event.preventDefault();
                setPage(1);
                setAppliedSearch(search.trim());
              }}
            >
              <Field label="Buscar">
                <input
                  type="search"
                  value={search}
                  placeholder="Nombre o correo…"
                  style={{ minWidth: 220 }}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </Field>
              <Field label="Rol">
                <select
                  value={roleFilter}
                  onChange={(event) => {
                    setRoleFilter(event.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Todos los roles</option>
                  {roles.map((role) => (
                    <option key={role.code} value={role.code}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </Field>
              <button type="submit" className="btn btn-primary btn-sm">
                Buscar
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setSearch('');
                  setAppliedSearch('');
                  setRoleFilter('');
                  setPage(1);
                }}
              >
                Limpiar
              </button>
            </form>

            {usersQuery.isLoading && <Loading label="Cargando usuarios…" />}
            {usersQuery.data && (
              <>
                <DataTable interpretationId="users"
                  columns={columns}
                  rows={users}
                  getKey={(row) => row.id}
                  empty="Sin usuarios que coincidan"
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem' }}>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={page <= 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                  >
                    ← Anterior
                  </button>
                  <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                    Página {usersQuery.data.page} de {usersQuery.data.pages || 1} ·{' '}
                    {num(usersQuery.data.total)} usuarios
                  </span>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={page >= (usersQuery.data.pages || 1)}
                    onClick={() => setPage((current) => current + 1)}
                  >
                    Siguiente →
                  </button>
                </div>
              </>
            )}
          </Card>

          <Card
            title="Matriz de permisos por rol"
            subtitle="Acciones autorizadas por módulo. El rol ADMIN posee todos los permisos."
            actions={<Badge tone="info">{permissions?.modules.length ?? 0} módulos</Badge>}
          >
            {permissionsQuery.isError && <ErrorBox message={errorMessage(permissionsQuery.error)} />}
            {permissionsQuery.isLoading && <Loading label="Cargando permisos…" />}
            {permissions && (
              <div className="table-wrap">
                <table className="data-table perm-table">
                  <thead>
                    <tr>
                      <th>Módulo</th>
                      {permissions.roles.map((role) => (
                        <th key={role.code}>{role.name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {permissions.modules
                      .filter((module) => module !== '*')
                      .map((module) => (
                        <tr key={module}>
                          <td style={{ fontWeight: 600 }}>
                            {module === 'ingestion' ? 'ingesta' : module}
                          </td>
                          {permissions.roles.map((role) => {
                            const actions =
                              permissions.matrix[role.code]?.[module] ??
                              permissions.matrix[role.code]?.['*'] ??
                              [];
                            return (
                              <td key={role.code}>
                                {actions.length === 0 ? (
                                  <span style={{ color: 'var(--muted)' }}>—</span>
                                ) : (
                                  <div className="perm-actions">
                                    {actions.map((action) => (
                                      <Badge key={action} tone="neutral">
                                        {action}
                                      </Badge>
                                    ))}
                                  </div>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                  </tbody>
                </table>
<Interpretation id="users" />
              </div>
            )}
          </Card>
        </div>

        <div>
          {selected ? (
            <>
              <Card
                title="Editar usuario"
                subtitle={selected.email}
                actions={
                  <button type="button" className="btn btn-sm" onClick={() => setSelected(null)}>
                    Cancelar
                  </button>
                }
              >
                <form onSubmit={handleUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  <Field label="Nombre completo">
                    <input
                      type="text"
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                    />
                  </Field>
                  <Field label="Rol">
                    <select value={newRole} onChange={(event) => setNewRole(event.target.value)}>
                      {roles.map((role) => (
                        <option key={role.code} value={role.code}>
                          {role.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="grid grid-2">
                    <Field label="Organización">
                      <input
                        type="text"
                        value={organization}
                        onChange={(event) => setOrganization(event.target.value)}
                      />
                    </Field>
                    <Field label="Cargo">
                      <input
                        type="text"
                        value={position}
                        onChange={(event) => setPosition(event.target.value)}
                      />
                    </Field>
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.84rem' }}>
                    <input
                      type="checkbox"
                      checked={isActive}
                      onChange={(event) => setIsActive(event.target.checked)}
                    />
                    Cuenta activa
                  </label>
                  <button type="submit" className="btn btn-primary" disabled={updateMutation.isPending}>
                    {updateMutation.isPending ? 'Guardando…' : 'Guardar cambios'}
                  </button>
                </form>
              </Card>

              <Card title="Restablecer contraseña" subtitle={`Forzar una nueva clave para ${selected.full_name}.`}>
                <form onSubmit={handleReset} style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                  <Field label="Nueva contraseña">
                    <input
                      type="password"
                      value={newPassword}
                      autoComplete="new-password"
                      placeholder="Mínimo 10 caracteres"
                      onChange={(event) => setNewPassword(event.target.value)}
                    />
                  </Field>
                  <small style={{ color: 'var(--muted)' }}>
                    Debe incluir mayúscula, minúscula, dígito y símbolo.
                  </small>
                  <button type="submit" className="btn" disabled={resetMutation.isPending || !newPassword}>
                    {resetMutation.isPending ? 'Restableciendo…' : 'Restablecer contraseña'}
                  </button>
                </form>
              </Card>
            </>
          ) : (
            <Card title="Crear usuario" subtitle="La cuenta se crea con el rol y la organización indicados.">
              <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <Field label="Correo institucional">
                  <input
                    type="email"
                    value={email}
                    autoComplete="off"
                    placeholder="usuario@nutririsk.ai"
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </Field>
                <Field label="Nombre completo">
                  <input
                    type="text"
                    value={fullName}
                    placeholder="Nombre y apellidos"
                    onChange={(event) => setFullName(event.target.value)}
                  />
                </Field>
                <Field label="Contraseña">
                  <input
                    type="password"
                    value={password}
                    autoComplete="new-password"
                    placeholder="Mínimo 10 caracteres"
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </Field>
                <Field label="Rol">
                  <select value={newRole} onChange={(event) => setNewRole(event.target.value)}>
                    {roles.map((role) => (
                      <option key={role.code} value={role.code}>
                        {role.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="grid grid-2">
                  <Field label="Organización">
                    <input
                      type="text"
                      value={organization}
                      placeholder="Ministerio de Salud"
                      onChange={(event) => setOrganization(event.target.value)}
                    />
                  </Field>
                  <Field label="Cargo">
                    <input
                      type="text"
                      value={position}
                      placeholder="Analista"
                      onChange={(event) => setPosition(event.target.value)}
                    />
                  </Field>
                </div>
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creando…' : 'Crear usuario'}
                </button>
                <small style={{ color: 'var(--muted)' }}>
                  La contraseña debe incluir mayúscula, minúscula, dígito y símbolo.
                </small>
              </form>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
