export const metadata = { title: 'About' };

export default function AboutPage() {
  return (
    <div className="space-y-4 max-w-2xl">
      <h2 className="text-3xl font-semibold">About BrainStack Studio</h2>
      <p>BrainStack Studio builds the BrainOps design system and automation templates to help teams launch faster.</p>
      <p>Our small but mighty team is passionate about empowering builders to operate intelligently.</p>
      <ul className="list-disc pl-6 space-y-1">
        <li><strong>Ash Ketchum</strong> – Founder & Strategy</li>
        <li><strong>Misty Waters</strong> – Product & Ops</li>
        <li><strong>Brock Stone</strong> – Engineering Lead</li>
      </ul>
    </div>
  );
}
