export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold tracking-tight text-content">{title}</h1>
      {description ? <p className="mt-1 text-sm text-content-muted">{description}</p> : null}
    </div>
  );
}
