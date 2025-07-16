export default function ErrorsList({ errors }) {
  if (!errors || errors.length === 0) return (
    <p className="italic text-sm opacity-70">No errors</p>
  );
  return (
    <ul className="text-red-600 list-disc list-inside space-y-1">
      {errors.map((e, i) => (
        <li key={i}>{e.error || JSON.stringify(e)}</li>
      ))}
    </ul>
  );
}
