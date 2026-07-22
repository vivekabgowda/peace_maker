'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  useEffect,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import {
  changePassword,
  getMe,
  logout as logoutRequest,
  logoutAll,
  updateProfile,
} from '@/features/settings/api';
import { ApiRequestError } from '@/lib/api/client';
import { ACCENT_PRESETS, DEFAULT_ACCENT, isValidAccent, setAccent } from '@/lib/theme/accent';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import type { Preferences, User } from '@/types';

/* --------------------------------- fields --------------------------------- */

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-content-muted">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-loss">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-content-faint">{hint}</span>
      ) : null}
    </label>
  );
}

const inputClass =
  'w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-content outline-none focus:border-accent disabled:opacity-60';

function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(inputClass, props.className)} />;
}

function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(inputClass, 'appearance-none', props.className)} />;
}

function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="text-sm text-content">{label}</p>
        {description ? <p className="text-xs text-content-faint">{description}</p> : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-5 w-9 shrink-0 rounded-full transition-colors',
          checked ? 'bg-accent' : 'bg-surface-border',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0.5',
          )}
        />
      </button>
    </div>
  );
}

function StatusLine({
  state,
  message,
}: {
  state: 'idle' | 'saving' | 'saved' | 'error';
  message?: string | null;
}) {
  if (state === 'idle') return null;
  const text =
    state === 'saving'
      ? 'Saving…'
      : state === 'saved'
        ? 'Saved'
        : (message ?? 'Something went wrong');
  return (
    <span
      className={cn(
        'text-xs',
        state === 'error' ? 'text-loss' : state === 'saved' ? 'text-gain' : 'text-content-muted',
      )}
    >
      {text}
    </span>
  );
}

function errMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Request failed';
}

/* ------------------------------- profile ---------------------------------- */

function ProfileSection({ user }: { user: User }) {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const [displayName, setDisplayName] = useState(user.profile?.display_name ?? '');

  const save = useMutation({
    mutationFn: () => updateProfile({ display_name: displayName.trim() || null }),
    onSuccess: (updated) => {
      qc.setQueryData(['me'], updated);
      setUser(updated);
    },
  });

  const dirty = (user.profile?.display_name ?? '') !== displayName;

  return (
    <Card>
      <CardHeader title="Profile" subtitle="Your name and account identity." />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Display name" hint="Shown in the app header and reports.">
          <TextInput
            value={displayName}
            maxLength={120}
            placeholder="e.g. Rajesh"
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </Field>
        <Field label="Email" hint="Email changes aren't available yet.">
          <TextInput value={user.email} disabled readOnly />
        </Field>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save profile'}
        </Button>
        <StatusLine
          state={
            save.isPending ? 'saving' : save.isError ? 'error' : save.isSuccess ? 'saved' : 'idle'
          }
          message={save.isError ? errMessage(save.error) : null}
        />
      </div>
    </Card>
  );
}

/* ----------------------------- change password ---------------------------- */

function PasswordSection() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');

  const mismatch = confirm.length > 0 && next !== confirm;
  const tooShort = next.length > 0 && next.length < 8;
  const canSubmit = current.length > 0 && next.length >= 8 && next === confirm;

  const save = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      setCurrent('');
      setNext('');
      setConfirm('');
    },
  });

  return (
    <Card>
      <CardHeader
        title="Password"
        subtitle="Changing your password signs you out of all other devices."
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Current password">
          <TextInput
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </Field>
        <Field label="New password" error={tooShort ? 'At least 8 characters.' : null}>
          <TextInput
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </Field>
        <Field label="Confirm new password" error={mismatch ? "Passwords don't match." : null}>
          <TextInput
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={!canSubmit || save.isPending}>
          {save.isPending ? 'Updating…' : 'Update password'}
        </Button>
        <StatusLine
          state={
            save.isPending ? 'saving' : save.isError ? 'error' : save.isSuccess ? 'saved' : 'idle'
          }
          message={save.isError ? errMessage(save.error) : 'Password updated'}
        />
      </div>
    </Card>
  );
}

/* ---------------------------- preferences saver --------------------------- */

/**
 * Shared hook: PATCHes a partial preferences change merged onto the current
 * server truth, so independent sections never clobber each other's fields.
 */
function usePreferencesSaver(current: Preferences) {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  return useMutation({
    mutationFn: (partial: Partial<Preferences>) =>
      updateProfile({ preferences: { ...current, ...partial } }),
    onSuccess: (updated) => {
      qc.setQueryData(['me'], updated);
      setUser(updated);
    },
  });
}

/* ------------------------------- trading ---------------------------------- */

const TIMEFRAMES: Preferences['preferred_timeframe'][] = ['1m', '5m', '15m', '1h', '1d'];

function TradingSection({ prefs }: { prefs: Preferences }) {
  const [risk, setRisk] = useState(String(prefs.default_risk_pct));
  const [loss, setLoss] = useState(String(prefs.daily_loss_limit_pct));
  const [maxTrades, setMaxTrades] = useState(String(prefs.max_open_trades));
  const [tf, setTf] = useState<Preferences['preferred_timeframe']>(prefs.preferred_timeframe);
  const save = usePreferencesSaver(prefs);

  const riskNum = Number(risk);
  const lossNum = Number(loss);
  const maxNum = Number(maxTrades);
  const riskErr = risk !== '' && (riskNum < 0.05 || riskNum > 20) ? 'Between 0.05 and 20%.' : null;
  const lossErr = loss !== '' && (lossNum < 0 || lossNum > 100) ? 'Between 0 and 100%.' : null;
  const maxErr =
    maxTrades !== '' && (!Number.isInteger(maxNum) || maxNum < 1 || maxNum > 100)
      ? 'A whole number, 1–100.'
      : null;
  const valid = !riskErr && !lossErr && !maxErr && risk !== '' && loss !== '' && maxTrades !== '';

  function onSave() {
    if (!valid) return;
    save.mutate({
      default_risk_pct: riskNum,
      daily_loss_limit_pct: lossNum,
      max_open_trades: maxNum,
      preferred_timeframe: tf,
    });
  }

  return (
    <Card>
      <CardHeader
        title="Trading"
        subtitle="Advisory risk defaults used when sizing paper trades. No live orders are ever placed."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Default risk %" error={riskErr} hint={riskErr ? undefined : 'Per trade.'}>
          <TextInput
            type="number"
            step="0.05"
            min={0.05}
            max={20}
            value={risk}
            onChange={(e) => setRisk(e.target.value)}
          />
        </Field>
        <Field
          label="Daily loss limit %"
          error={lossErr}
          hint={lossErr ? undefined : 'Of capital.'}
        >
          <TextInput
            type="number"
            step="0.5"
            min={0}
            max={100}
            value={loss}
            onChange={(e) => setLoss(e.target.value)}
          />
        </Field>
        <Field label="Max open trades" error={maxErr}>
          <TextInput
            type="number"
            step="1"
            min={1}
            max={100}
            value={maxTrades}
            onChange={(e) => setMaxTrades(e.target.value)}
          />
        </Field>
        <Field label="Preferred timeframe">
          <Select
            value={tf}
            onChange={(e) => setTf(e.target.value as Preferences['preferred_timeframe'])}
          >
            {TIMEFRAMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={onSave} disabled={!valid || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save trading settings'}
        </Button>
        <StatusLine
          state={
            save.isPending ? 'saving' : save.isError ? 'error' : save.isSuccess ? 'saved' : 'idle'
          }
          message={save.isError ? errMessage(save.error) : null}
        />
      </div>
    </Card>
  );
}

/* ---------------------------- notifications ------------------------------- */

function NotificationsSection({ prefs }: { prefs: Preferences }) {
  const [email, setEmail] = useState(prefs.notify_email);
  const [trade, setTrade] = useState(prefs.notify_trade);
  const [browser, setBrowser] = useState(prefs.notify_browser);
  const [permissionHint, setPermissionHint] = useState<string | null>(null);
  const save = usePreferencesSaver(prefs);

  const browserSupported = typeof window !== 'undefined' && 'Notification' in window;

  async function onToggleBrowser(nextValue: boolean) {
    setPermissionHint(null);
    if (nextValue && browserSupported) {
      const result = await Notification.requestPermission();
      if (result !== 'granted') {
        setBrowser(false);
        setPermissionHint('Browser notifications were blocked in your browser settings.');
        return;
      }
    }
    setBrowser(nextValue);
  }

  const dirty =
    email !== prefs.notify_email ||
    trade !== prefs.notify_trade ||
    browser !== prefs.notify_browser;

  return (
    <Card>
      <CardHeader title="Notifications" subtitle="Choose how you want to be alerted." />
      <div className="divide-y divide-surface-border/60">
        <Toggle
          label="Email alerts"
          description="Daily and weekly performance summaries by email."
          checked={email}
          onChange={setEmail}
        />
        <Toggle
          label="Trade alerts"
          description="Notify when a paper trade opens, closes, or hits a stop/target."
          checked={trade}
          onChange={setTrade}
        />
        <Toggle
          label="Browser notifications"
          description={
            browserSupported
              ? 'Desktop push while the app is open.'
              : 'Not supported in this browser.'
          }
          checked={browser}
          onChange={onToggleBrowser}
          disabled={!browserSupported}
        />
      </div>
      {permissionHint ? <p className="mt-2 text-xs text-caution">{permissionHint}</p> : null}
      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={() =>
            save.mutate({ notify_email: email, notify_trade: trade, notify_browser: browser })
          }
          disabled={!dirty || save.isPending}
        >
          {save.isPending ? 'Saving…' : 'Save notifications'}
        </Button>
        <StatusLine
          state={
            save.isPending ? 'saving' : save.isError ? 'error' : save.isSuccess ? 'saved' : 'idle'
          }
          message={save.isError ? errMessage(save.error) : null}
        />
      </div>
    </Card>
  );
}

/* ------------------------------ appearance -------------------------------- */

function AppearanceSection({ prefs }: { prefs: Preferences }) {
  const [accent, setAccentDraft] = useState(
    isValidAccent(prefs.accent) ? prefs.accent : DEFAULT_ACCENT,
  );
  const save = usePreferencesSaver(prefs);

  // Live preview: apply the draft accent as the user clicks swatches.
  useEffect(() => {
    setAccent(accent);
  }, [accent]);

  const dirty = accent.toLowerCase() !== prefs.accent.toLowerCase();

  return (
    <Card>
      <CardHeader title="Appearance" subtitle="Personalise the look of the terminal." />

      <div className="mb-5">
        <p className="mb-2 text-xs font-medium text-content-muted">Theme</p>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-accent bg-accent/10 px-3 py-2 text-sm text-content"
            aria-pressed="true"
          >
            Dark
          </button>
          <button
            type="button"
            disabled
            className="flex cursor-not-allowed items-center gap-2 rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-content-faint"
          >
            Light
            <span className="rounded-full border border-surface-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
              Soon
            </span>
          </button>
        </div>
        <p className="mt-1 text-xs text-content-faint">
          Light mode is on the roadmap; the terminal is dark-only for now.
        </p>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium text-content-muted">Accent colour</p>
        <div className="flex flex-wrap items-center gap-2">
          {ACCENT_PRESETS.map((preset) => {
            const active = preset.value.toLowerCase() === accent.toLowerCase();
            return (
              <button
                key={preset.value}
                type="button"
                title={preset.label}
                aria-label={preset.label}
                aria-pressed={active}
                onClick={() => setAccentDraft(preset.value)}
                className={cn(
                  'h-8 w-8 rounded-full border-2 transition-transform hover:scale-110',
                  active ? 'border-content' : 'border-transparent',
                )}
                style={{ backgroundColor: preset.value }}
              />
            );
          })}
          <label className="ml-1 flex items-center gap-2 text-xs text-content-faint">
            Custom
            <input
              type="color"
              value={accent}
              onChange={(e) => setAccentDraft(e.target.value)}
              className="h-8 w-8 cursor-pointer rounded border border-surface-border bg-transparent p-0"
              aria-label="Custom accent colour"
            />
          </label>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-3">
        <Button onClick={() => save.mutate({ accent })} disabled={!dirty || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save appearance'}
        </Button>
        {dirty ? (
          <button
            type="button"
            className="text-xs text-content-muted hover:text-content"
            onClick={() => setAccentDraft(prefs.accent)}
          >
            Reset
          </button>
        ) : null}
        <StatusLine
          state={
            save.isPending ? 'saving' : save.isError ? 'error' : save.isSuccess ? 'saved' : 'idle'
          }
          message={save.isError ? errMessage(save.error) : null}
        />
      </div>
    </Card>
  );
}

/* ------------------------------- security --------------------------------- */

function SecuritySection() {
  const router = useRouter();
  const clear = useAuthStore((s) => s.clear);

  const signOut = useMutation({
    mutationFn: () => logoutRequest(),
    onSettled: () => {
      clear();
      router.push('/login');
    },
  });

  const signOutEverywhere = useMutation({
    mutationFn: () => logoutAll(),
    onSettled: () => {
      clear();
      router.push('/login');
    },
  });

  return (
    <Card>
      <CardHeader
        title="Security"
        subtitle="Session management. Sessions use short-lived access tokens with a rotating httpOnly refresh cookie."
      />
      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-content">This device</p>
            <p className="text-xs text-content-faint">End your session on this browser.</p>
          </div>
          <Button
            variant="secondary"
            onClick={() => signOut.mutate()}
            disabled={signOut.isPending || signOutEverywhere.isPending}
          >
            {signOut.isPending ? 'Signing out…' : 'Sign out'}
          </Button>
        </div>
        <div className="flex flex-col gap-3 border-t border-surface-border/60 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-content">All devices</p>
            <p className="text-xs text-content-faint">
              Revoke every active session. Use this if you suspect your account is compromised.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => signOutEverywhere.mutate()}
            disabled={signOut.isPending || signOutEverywhere.isPending}
            className="border-loss/40 text-loss hover:bg-loss/10"
          >
            {signOutEverywhere.isPending ? 'Revoking…' : 'Log out everywhere'}
          </Button>
        </div>
      </div>
    </Card>
  );
}

/* --------------------------------- view ----------------------------------- */

export function SettingsView() {
  const { data: user, isLoading, isError, error } = useQuery({ queryKey: ['me'], queryFn: getMe });

  if (isLoading) {
    return <Card className="text-sm text-content-muted">Loading your settings…</Card>;
  }
  if (isError || !user) {
    return (
      <Card className="text-sm text-loss">
        Could not load your settings: {error ? errMessage(error) : 'unknown error'}
      </Card>
    );
  }

  const prefs = user.profile?.preferences;

  return (
    <div className="max-w-4xl space-y-6">
      <ProfileSection user={user} />
      <PasswordSection />
      {prefs ? (
        <>
          <TradingSection prefs={prefs} />
          <NotificationsSection prefs={prefs} />
          <AppearanceSection prefs={prefs} />
        </>
      ) : (
        <Card className="text-sm text-content-muted">
          Preferences are unavailable for this account.
        </Card>
      )}
      <SecuritySection />
    </div>
  );
}
