'use client';

/**
 * Root error boundary. Catches render errors that escape every nested boundary
 * (including in the root layout) so the app degrades to a recoverable screen
 * instead of a blank page. Must render its own <html>/<body>.
 */
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          background: '#0d1117',
          color: '#e6edf3',
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        <div style={{ maxWidth: 420, padding: 24, textAlign: 'center' }}>
          <h1 style={{ fontSize: 18, fontWeight: 600 }}>Something went wrong</h1>
          <p style={{ marginTop: 8, fontSize: 14, color: '#8b98a9' }}>
            An unexpected error occurred. You can try again — your session is preserved.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 20,
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: '#1f6feb',
              color: '#fff',
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
