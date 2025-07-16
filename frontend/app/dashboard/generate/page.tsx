import React from 'react';
import ContentGenerator from '../../../components/ContentGenerator';

export default function GeneratePage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Generate Content</h2>
      <ContentGenerator />
    </div>
  );
}
