'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';

import { Card, CardHeader } from '@/components/ui/Card';
import {
  getAudit,
  getCommitteeConfig,
  getLogs,
  getPermissions,
  getSystemHealth,
  getUsers,
  updateCommitteeConfig,
  updateUserRole,
  type CommitteeAgentConfig,
  type LogRecord,
  type ServiceStatus,
} from '@/features/admin/api';
import { ApiRequestError } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';

function errMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Request failed';
}

function labelize(value: string): string {
  return value.replace(/_/g, ' ');
}

function fmtTime(value: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('en-IN', { hour12: false });
}

/* --------------------------------- tabs ----------------------------------- */

const TABS = ['System', 'Users', 'AI Committee', 'Logs', 'Audit'] as const;
type Tab = (typeof TABS)[number];

/* ----------------------------- system health ------------------------------ */

function ServiceCard({ s }: { s: ServiceStatus }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium capitalize text-content">{labelize(s.name)}</span>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
            s.healthy ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss',
          )}
        >
          <span className={cn('h-1.5 w-1.5 rounded-full', s.healthy ? 'bg-gain' : 'bg-loss')} />
          {s.healthy ? 'Healthy' : 'Down'}
        </span>
      </div>
      <p className="mt-1 text-xs text-content-muted">{s.kind}</p>
      <p className="mt-2 text-xs text-content-faint">{s.detail}</p>
      {s.latency_ms != null ? (
        <p className="tabular mt-1 text-xs text-content-faint">{s.latency_ms} ms</p>
      ) : null}
    </Card>
  );
}

function SystemPanel() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['admin-system'],
    queryFn: getSystemHealth,
    refetchInterval: 15000,
  });

  if (isLoading) return <Card className="text-sm text-content-muted">Checking subsystems…</Card>;
  if (isError || !data)
    return (
      <Card className="text-sm text-loss">Could not load system health: {errMessage(error)}</Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-content-muted">
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold',
            data.status === 'healthy' ? 'bg-gain/10 text-gain' : 'bg-caution/10 text-caution',
          )}
        >
          {data.status === 'healthy' ? 'All systems operational' : 'Degraded'}
        </span>
        <span>
          Env <span className="text-content">{data.environment}</span>
        </span>
        <span>
          Version <span className="tabular text-content">{data.version}</span>
        </span>
        <span>
          Feed <span className="text-content">{data.market_provider}</span>
        </span>
        <span>
          Broker{' '}
          <span className="text-content">
            {data.broker_connected ? 'connected' : 'advisory-only (disconnected)'}
          </span>
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.services.map((s) => (
          <ServiceCard key={s.name} s={s} />
        ))}
      </div>
    </div>
  );
}

/* --------------------------------- users ---------------------------------- */

function UsersPanel() {
  const qc = useQueryClient();
  const myId = useAuthStore((s) => s.user?.id);
  const usersQuery = useQuery({ queryKey: ['admin-users'], queryFn: getUsers });
  const permsQuery = useQuery({ queryKey: ['admin-permissions'], queryFn: getPermissions });
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutate = useMutation({
    mutationFn: ({ id, role }: { id: string; role: 'user' | 'admin' }) => updateUserRole(id, role),
    onMutate: ({ id }) => {
      setPendingId(id);
      setErrorMsg(null);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
    onError: (e) => setErrorMsg(errMessage(e)),
    onSettled: () => setPendingId(null),
  });

  if (usersQuery.isLoading)
    return <Card className="text-sm text-content-muted">Loading users…</Card>;
  if (usersQuery.isError || !usersQuery.data)
    return (
      <Card className="text-sm text-loss">
        Could not load users: {errMessage(usersQuery.error)}
      </Card>
    );

  return (
    <div className="space-y-6">
      {errorMsg ? <Card className="text-sm text-loss">{errorMsg}</Card> : null}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-surface-border text-left text-xs text-content-muted">
              <th className="px-4 py-3 font-medium">User</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">MFA</th>
              <th className="px-4 py-3 font-medium">Joined</th>
              <th className="px-4 py-3 text-right font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {usersQuery.data.map((u) => {
              const isSelf = u.id === myId;
              const nextRole = u.role === 'admin' ? 'user' : 'admin';
              return (
                <tr key={u.id} className="border-b border-surface-border/50 last:border-0">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-content">{u.display_name ?? u.email}</div>
                    {u.display_name ? (
                      <div className="text-xs text-content-faint">{u.email}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs font-medium',
                        u.role === 'admin'
                          ? 'border-accent/40 bg-accent/10 text-accent'
                          : 'border-surface-border bg-surface-overlay text-content-muted',
                      )}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-content-muted">{u.status}</td>
                  <td className="px-4 py-2.5 text-content-muted">{u.mfa_enabled ? 'on' : 'off'}</td>
                  <td className="px-4 py-2.5 text-content-muted">
                    {new Date(u.created_at).toLocaleDateString('en-IN')}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {isSelf ? (
                      <span className="text-xs text-content-faint">you</span>
                    ) : (
                      <button
                        type="button"
                        disabled={pendingId === u.id}
                        onClick={() => mutate.mutate({ id: u.id, role: nextRole })}
                        className="rounded-md border border-surface-border bg-surface-overlay px-2.5 py-1 text-xs text-content hover:bg-surface-border disabled:opacity-50"
                      >
                        {pendingId === u.id
                          ? 'Saving…'
                          : nextRole === 'admin'
                            ? 'Make admin'
                            : 'Make user'}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      <Card>
        <CardHeader title="Roles & permissions" subtitle="What each role is allowed to do (RBAC)" />
        {permsQuery.data ? (
          <div className="grid gap-4 md:grid-cols-2">
            {permsQuery.data.roles.map((r) => (
              <div key={r.role} className="rounded-md border border-surface-border bg-surface p-3">
                <p className="mb-2 text-sm font-semibold capitalize text-content">{r.role}</p>
                <ul className="flex flex-wrap gap-1.5">
                  {r.permissions.map((p) => (
                    <li
                      key={p}
                      className="rounded bg-surface-overlay px-2 py-0.5 text-xs text-content-muted"
                    >
                      {labelize(p)}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-content-muted">Loading permissions…</p>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------ AI committee ------------------------------ */

function CommitteePanel() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['admin-committee-config'],
    queryFn: getCommitteeConfig,
  });

  const [agents, setAgents] = useState<CommitteeAgentConfig[]>([]);
  const [strong, setStrong] = useState('0.6');
  const [act, setAct] = useState('0.35');

  useEffect(() => {
    if (data) {
      setAgents(data.agents.map((a) => ({ ...a })));
      setStrong(String(data.thresholds.strong));
      setAct(String(data.thresholds.act));
    }
  }, [data]);

  const save = useMutation({
    mutationFn: () =>
      updateCommitteeConfig({
        agents: agents.map((a) => ({ role: a.role, enabled: a.enabled, weight: a.weight })),
        thresholds: { strong: Number(strong), act: Number(act) },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-committee-config'] }),
  });

  if (isLoading)
    return <Card className="text-sm text-content-muted">Loading committee config…</Card>;
  if (isError || !data)
    return (
      <Card className="text-sm text-loss">
        Could not load committee config: {errMessage(error)}
      </Card>
    );

  const strongN = Number(strong);
  const actN = Number(act);
  const enabledCount = agents.filter((a) => a.enabled).length;
  const thresholdsValid = strongN > 0 && strongN < 1 && actN > 0 && actN < 1 && actN < strongN;
  const weightsValid = agents.every((a) => a.weight >= 0 && a.weight <= 5);
  const valid = enabledCount >= 1 && thresholdsValid && weightsValid;

  function setAgent(role: string, patch: Partial<CommitteeAgentConfig>) {
    setAgents((prev) => prev.map((a) => (a.role === role ? { ...a, ...patch } : a)));
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Agents"
          subtitle="Enable or disable each specialist and tune its weight in the CIO's vote. Changes apply to the next deliberation."
        />
        <div className="space-y-2">
          {agents.map((a) => (
            <div
              key={a.role}
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-surface-border bg-surface p-3"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-content">{a.name}</p>
                <p className="text-xs capitalize text-content-faint">{labelize(a.role)}</p>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-content-muted">
                  Weight
                  <input
                    type="number"
                    step="0.1"
                    min={0}
                    max={5}
                    value={a.weight}
                    onChange={(e) => setAgent(a.role, { weight: Number(e.target.value) })}
                    className="tabular w-20 rounded-md border border-surface-border bg-surface px-2 py-1 text-sm text-content outline-none focus:border-accent"
                  />
                </label>
                <button
                  type="button"
                  role="switch"
                  aria-checked={a.enabled}
                  aria-label={`Toggle ${a.name}`}
                  onClick={() => setAgent(a.role, { enabled: !a.enabled })}
                  className={cn(
                    'relative h-5 w-9 shrink-0 rounded-full transition-colors',
                    a.enabled ? 'bg-accent' : 'bg-surface-border',
                  )}
                >
                  <span
                    className={cn(
                      'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform',
                      a.enabled ? 'translate-x-4' : 'translate-x-0.5',
                    )}
                  />
                </button>
              </div>
            </div>
          ))}
        </div>
        {enabledCount < 1 ? (
          <p className="mt-2 text-xs text-loss">At least one agent must stay enabled.</p>
        ) : null}
      </Card>

      <Card>
        <CardHeader
          title="Confidence thresholds"
          subtitle="Signed consensus needed to act. 'Strong' → strong buy/sell; 'Act' → buy/sell; below 'Act' → hold."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-content-muted">
              Strong conviction (0–1)
            </span>
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={strong}
              onChange={(e) => setStrong(e.target.value)}
              className="tabular w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-content outline-none focus:border-accent"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-content-muted">
              Act threshold (0–1)
            </span>
            <input
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={act}
              onChange={(e) => setAct(e.target.value)}
              className="tabular w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-content outline-none focus:border-accent"
            />
          </label>
        </div>
        {!thresholdsValid ? (
          <p className="mt-2 text-xs text-loss">
            Both must be between 0 and 1, and Act must be below Strong.
          </p>
        ) : null}
      </Card>

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={!valid || save.isPending}
          onClick={() => save.mutate()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {save.isPending ? 'Saving…' : 'Save committee config'}
        </button>
        {save.isSuccess ? <span className="text-xs text-gain">Saved</span> : null}
        {save.isError ? <span className="text-xs text-loss">{errMessage(save.error)}</span> : null}
        <span className="text-xs text-content-faint">
          {data.customized ? 'Custom configuration active' : 'Using built-in defaults'}
        </span>
      </div>
    </div>
  );
}

/* --------------------------------- logs ----------------------------------- */

const LEVEL_STYLES: Record<string, string> = {
  debug: 'text-content-faint',
  info: 'text-content-muted',
  warning: 'text-caution',
  error: 'text-loss',
  critical: 'text-loss',
};

function LogRow({ r }: { r: LogRecord }) {
  return (
    <div className="flex gap-3 border-b border-surface-border/40 px-4 py-2 text-xs last:border-0">
      <span className="tabular shrink-0 text-content-faint">{fmtTime(r.timestamp)}</span>
      <span
        className={cn(
          'w-16 shrink-0 font-medium uppercase',
          LEVEL_STYLES[r.level] ?? 'text-content-muted',
        )}
      >
        {r.level}
      </span>
      <span className="min-w-0 flex-1 text-content">
        {r.event}
        {r.logger ? <span className="ml-2 text-content-faint">· {r.logger}</span> : null}
      </span>
    </div>
  );
}

function LogsPanel() {
  const [level, setLevel] = useState('info');
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['admin-logs', level],
    queryFn: () => getLogs(level, 200),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-content-muted">Minimum level</span>
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="appearance-none rounded-md border border-surface-border bg-surface px-3 py-1.5 text-sm text-content outline-none focus:border-accent"
        >
          {['debug', 'info', 'warning', 'error'].map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>
      {isLoading ? (
        <Card className="text-sm text-content-muted">Loading logs…</Card>
      ) : isError ? (
        <Card className="text-sm text-loss">Could not load logs: {errMessage(error)}</Card>
      ) : !data || data.length === 0 ? (
        <Card className="text-sm text-content-muted">
          No log records at this level yet. The buffer fills as the app handles requests.
        </Card>
      ) : (
        <Card className="p-0">
          <div className="max-h-[28rem] overflow-y-auto font-mono">
            {data.map((r, i) => (
              <LogRow key={`${r.timestamp}-${i}`} r={r} />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

/* --------------------------------- audit ---------------------------------- */

function AuditPanel() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['admin-audit'],
    queryFn: () => getAudit(100),
    refetchInterval: 20000,
  });

  if (isLoading) return <Card className="text-sm text-content-muted">Loading audit trail…</Card>;
  if (isError)
    return <Card className="text-sm text-loss">Could not load audit: {errMessage(error)}</Card>;
  if (!data || data.length === 0)
    return (
      <Card className="text-sm text-content-muted">
        <p className="font-medium text-content">No audit entries yet.</p>
        <p className="mt-1">
          Privileged actions — role changes and committee-config edits — are recorded here with the
          actor, target and what changed.
        </p>
      </Card>
    );

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-xs text-content-muted">
            <th className="px-4 py-3 font-medium">When</th>
            <th className="px-4 py-3 font-medium">Actor</th>
            <th className="px-4 py-3 font-medium">Action</th>
            <th className="px-4 py-3 font-medium">Target</th>
            <th className="px-4 py-3 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {data.map((a) => (
            <tr key={a.id} className="border-b border-surface-border/50 last:border-0">
              <td className="tabular px-4 py-2.5 text-content-muted">{fmtTime(a.created_at)}</td>
              <td className="px-4 py-2.5 text-content-muted">{a.actor_email ?? '—'}</td>
              <td className="px-4 py-2.5 text-content">{labelize(a.action)}</td>
              <td className="px-4 py-2.5 text-content-muted">{a.target ?? '—'}</td>
              <td className="px-4 py-2.5 text-content-faint">
                <code className="text-xs">{JSON.stringify(a.detail)}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

/* --------------------------------- view ----------------------------------- */

function TabPanel({ tab }: { tab: Tab }): ReactNode {
  switch (tab) {
    case 'System':
      return <SystemPanel />;
    case 'Users':
      return <UsersPanel />;
    case 'AI Committee':
      return <CommitteePanel />;
    case 'Logs':
      return <LogsPanel />;
    case 'Audit':
      return <AuditPanel />;
  }
}

export function AdminView() {
  const [tab, setTab] = useState<Tab>('System');
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-1 border-b border-surface-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors',
              tab === t
                ? 'border-accent text-content'
                : 'border-transparent text-content-muted hover:text-content',
            )}
          >
            {t}
          </button>
        ))}
      </div>
      <TabPanel tab={tab} />
    </div>
  );
}
