import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Layout from '../components/Layout';
import StatusCards from '../components/StatusCards';
import MemoryChart from '../components/MemoryChart';
import TaskList from '../components/TaskList';
import ErrorsList from '../components/ErrorsList';
import FeedbackForm from '../components/FeedbackForm';
import OnboardingOverlay from '../components/OnboardingOverlay';
import SearchBar from '../components/SearchBar';
import { apiFetch } from '../lib/api';

export default function Home({ theme, setTheme }) {
  const [metrics, setMetrics] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(true);
  const load = async () => {
    try {
      const [m, t, e] = await Promise.all([
        apiFetch('/dashboard/metrics'),
        apiFetch('/dashboard/tasks'),
        apiFetch('/logs/errors?limit=5')
      ]);
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
        <motion.div className="grid gap-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <StatusCards metrics={metrics} />
          <MemoryChart metrics={metrics} />
          <SearchBar />
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
        </motion.div>
      )}
    </Layout>
  );
}
