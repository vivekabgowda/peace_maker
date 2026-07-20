'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { Button } from '@/components/ui/Button';
import { ApiRequestError } from '@/lib/api/client';
import { login, register } from '@/lib/auth/api';
import { useAuthStore } from '@/stores/authStore';

type Mode = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === 'register') {
        const { tokens, user } = await register(email, password);
        setSession(tokens, user);
      } else {
        const tokens = await login(email, password);
        setSession(tokens);
      }
      router.replace('/dashboard');
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-surface p-4">
      <div className="w-full max-w-sm rounded-md border border-surface-border bg-surface-raised p-8">
        <div className="mb-6 flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded bg-accent text-xs font-bold text-white">
            BKN
          </span>
          <div>
            <h1 className="text-sm font-semibold">AI Capital</h1>
            <p className="text-xs text-content-muted">
              {mode === 'login' ? 'Sign in to continue' : 'Create your account'}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs text-content-muted">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-content-muted">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </label>

          {error ? <p className="text-xs text-loss">{error}</p> : null}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </Button>
        </form>

        <button
          type="button"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          className="mt-4 w-full text-center text-xs text-content-muted hover:text-content"
        >
          {mode === 'login'
            ? "Don't have an account? Register"
            : 'Already have an account? Sign in'}
        </button>
      </div>
    </div>
  );
}
