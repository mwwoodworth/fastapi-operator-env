export default function TaskList({ tasks }) {
  if (!tasks || tasks.length === 0) return (
    <p className="italic text-sm opacity-70">No tasks found</p>
  );
  return (
    <ul className="space-y-1 list-disc list-inside">
      {tasks.map((t, i) => (
        <li key={i}>{t.task || JSON.stringify(t)}</li>
      ))}
    </ul>
  );
}
