import { useEffect, useState } from 'react';

export default function OnboardingOverlay() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('onboarded')) setVisible(true);
  }, []);

  const dismiss = () => {
    localStorage.setItem('onboarded', '1');
    setVisible(false);
  };

  if (!visible) return null;
  return (
    <div className="fixed inset-0 bg-black/70 text-white flex flex-col items-center justify-center z-50 p-4">
      <div className="max-w-md text-center space-y-4">
        <h2 className="text-2xl font-bold">Welcome!</h2>
        <p>Use this dashboard to monitor tasks and submit feedback. Data refreshes every few seconds.</p>
        <button className="px-4 py-2 bg-blue-600 rounded" onClick={dismiss}>Got it</button>
      </div>
    </div>
  );
}
