export const metadata = { title: 'Services' };

export default function ServicesPage() {
  return (
    <div className="space-y-4 max-w-2xl">
      <h2 className="text-3xl font-semibold">Services</h2>
      <p>BrainStack Studio offers automation consulting, custom template development and integration support to help you launch faster.</p>
      <ul className="list-disc pl-6 space-y-1">
        <li>Automation strategy workshops</li>
        <li>Custom BrainOps template builds</li>
        <li>Integration and onboarding assistance</li>
      </ul>
    </div>
  );
}
