import React from 'react';
import SEOInsights from '../../../components/SEOInsights';
import ResearchQueue from '../../../components/ResearchQueue';

export default function InsightsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Insights</h2>
      <SEOInsights />
      <ResearchQueue />
    </div>
  );
}
