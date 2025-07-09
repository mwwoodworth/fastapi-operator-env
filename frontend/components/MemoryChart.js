import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

export default function MemoryChart({ metrics }) {
  if (!metrics) return null;
  const data = [
    { name: 'Tasks', value: metrics.tasks_logged },
    { name: 'Errors', value: metrics.errors_logged },
    { name: 'Memory', value: metrics.memory_entries }
  ];
  const colors = ['#3b82f6', '#ef4444', '#10b981'];
  return (
    <div className="w-full h-64">
      <ResponsiveContainer>
        <PieChart>
          <Pie dataKey="value" data={data} outerRadius={80} label>
            {data.map((_, i) => (
              <Cell key={i} fill={colors[i % colors.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
