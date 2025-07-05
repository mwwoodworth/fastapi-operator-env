import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import StatusCards from '../components/StatusCards';
import MemoryChart from '../components/MemoryChart';
import TaskList from '../components/TaskList';
import ErrorsList from '../components/ErrorsList';
import FeedbackForm from '../components/FeedbackForm';
import OnboardingOverlay from '../components/OnboardingOverlay';

export default function Home({ theme, setTheme }) {
  const [metrics, setMetrics] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(true);
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';

  const load = async () => {
    try {
      const [mRes, tRes, eRes] = await Promise.all([
        fetch(`${API_BASE}/dashboard/metrics`),
        fetch(`${API_BASE}/dashboard/tasks`),
        fetch(`${API_BASE}/logs/errors?limit=5`)
      ]);
      const m = await mRes.json();
      const t = await tRes.json();
      const e = await eRes.json();
      setMetrics(m);
      setTasks(t.tasks || t);
      setErrors(e.entries || e);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <Layout theme={theme} setTheme={setTheme}>
      <OnboardingOverlay />
      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="grid gap-4">
          <StatusCards metrics={metrics} />
          <MemoryChart metrics={metrics} />
          <section>
            <h2 className="font-semibold mb-2">Tasks</h2>
            <TaskList tasks={tasks} />
          </section>
          <section>
            <h2 className="font-semibold mb-2">Recent Errors</h2>
            <ErrorsList errors={errors} />
          </section>
          <section>
            <h2 className="font-semibold mb-2">Send Feedback</h2>
            <FeedbackForm />
          </section>
        </div>
      )}
    </Layout>
  );
}
