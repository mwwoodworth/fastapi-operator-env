import React from 'react';
import ClaudePipeline from '../../../components/ClaudePipeline';

export default function PipelinePage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Claude Pipelines</h2>
      <ClaudePipeline />
    </div>
  );
}
