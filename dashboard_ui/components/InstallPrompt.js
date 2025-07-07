import { useEffect, useState } from 'react';

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);

  useEffect(() => {
    const handler = (e) => {
      e.preventDefault();
      setDeferred(e);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  if (!deferred) return null;

  const install = () => {
    deferred.prompt();
    setDeferred(null);
  };

  return (
    <div className="fixed bottom-4 right-4 bg-blue-600 text-white p-3 rounded shadow" role="dialog" aria-label="Install App Prompt">
      <button onClick={install} className="font-semibold" title="Install as PWA">Install App</button>
    </div>
  );
}
