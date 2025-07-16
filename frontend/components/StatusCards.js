export default function StatusCards({ metrics }) {
  if (!metrics) return null;
  const cards = [
    { label: 'Tasks Logged', value: metrics.tasks_logged },
    { label: 'Errors', value: metrics.errors_logged },
    { label: 'Memory Entries', value: metrics.memory_entries }
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {cards.map(c => (
        <div key={c.label} className="border rounded p-4 text-center">
          <p className="text-sm opacity-70">{c.label}</p>
          <p className="text-2xl font-semibold">{c.value ?? 0}</p>
        </div>
      ))}
    </div>
  );
}
