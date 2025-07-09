import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function MetricsHistoryChart({ history }) {
  if (!history.length) return null;
  return (
    <div className="w-full h-48">
      <ResponsiveContainer>
        <LineChart data={history}>
          <XAxis dataKey="time" hide />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="memory_entries" stroke="#3b82f6" />
          <Line type="monotone" dataKey="claude_logs" stroke="#ef4444" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
