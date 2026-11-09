export default function AuthCard({ title, subtitle, error, children }) {
  return (
    <section className="bg-mist px-5 py-14">
      <div className="card mx-auto max-w-md p-8">
        <h1 className="text-2xl font-bold text-navy">{title}</h1>
        <p className="mt-1 text-sm">{subtitle}</p>
        {error && (
          <p role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        {children}
      </div>
    </section>
  )
}

export function Field({ label, ...props }) {
  return (
    <label className="mt-4 block text-sm font-medium">
      {label}
      <input
        {...props}
        className="mt-1 w-full rounded-lg border border-navy/20 px-3 py-2 text-base focus:border-accent"
      />
    </label>
  )
}
