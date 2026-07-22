import { apiFetch } from '@/lib/api/client';

export interface ServiceStatus {
  name: string;
  kind: string;
  healthy: boolean;
  detail: string;
  latency_ms: number | null;
  meta: Record<string, unknown>;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded';
  version: string;
  environment: string;
  timestamp: string;
  market_provider: string;
  broker_connected: boolean;
  services: ServiceStatus[];
}

export interface AdminUser {
  id: string;
  email: string;
  role: 'user' | 'admin';
  status: string;
  mfa_enabled: boolean;
  created_at: string;
  display_name: string | null;
}

export interface RolePermissions {
  roles: { role: string; permissions: string[] }[];
}

export interface CommitteeAgentConfig {
  role: string;
  name: string;
  enabled: boolean;
  weight: number;
}

export interface CommitteeConfig {
  agents: CommitteeAgentConfig[];
  thresholds: { strong: number; act: number };
  customized: boolean;
}

export interface LogRecord {
  timestamp: string | null;
  level: string;
  event: string;
  logger: string | null;
  correlation_id: string | null;
}

export interface AuditRecord {
  id: number;
  actor_email: string | null;
  action: string;
  target: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export const getSystemHealth = () => apiFetch<SystemHealth>('/admin/system', { auth: true });

export const getUsers = () =>
  apiFetch<{ users: AdminUser[] }>('/admin/users', { auth: true }).then((r) => r.users);

export const getPermissions = () => apiFetch<RolePermissions>('/admin/permissions', { auth: true });

export const updateUserRole = (userId: string, role: 'user' | 'admin') =>
  apiFetch<AdminUser>(`/admin/users/${userId}/role`, {
    method: 'PATCH',
    body: { role },
    auth: true,
  });

export const getCommitteeConfig = () =>
  apiFetch<CommitteeConfig>('/admin/committee/config', { auth: true });

export const updateCommitteeConfig = (payload: {
  agents: { role: string; enabled: boolean; weight: number }[];
  thresholds: { strong: number; act: number };
}) =>
  apiFetch<CommitteeConfig>('/admin/committee/config', {
    method: 'PUT',
    body: payload,
    auth: true,
  });

export const getLogs = (level = 'info', limit = 100) =>
  apiFetch<{ logs: LogRecord[] }>(`/admin/logs?level=${level}&limit=${limit}`, {
    auth: true,
  }).then((r) => r.logs);

export const getAudit = (limit = 100) =>
  apiFetch<{ audit: AuditRecord[] }>(`/admin/audit?limit=${limit}`, { auth: true }).then(
    (r) => r.audit,
  );
