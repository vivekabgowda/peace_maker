/**
 * Shared application types.
 *
 * NOTE: From Sprint 2 onward, request/response types are generated from the
 * backend OpenAPI schema so the contract never drifts. These hand-written types
 * cover the Sprint 1 auth surface only.
 */

export interface UserProfile {
  display_name: string | null;
  trading_capital: string;
  experience_level: string | null;
  timezone: string;
}

export interface User {
  id: string;
  email: string;
  role: 'user' | 'admin';
  status: string;
  mfa_enabled: boolean;
  created_at: string;
  profile: UserProfile | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    correlation_id: string | null;
  };
}
