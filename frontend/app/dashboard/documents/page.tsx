import React from 'react';
import DocumentBrowser from '../../../components/DocumentBrowser';

export default function DocumentsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Documents</h2>
      <DocumentBrowser />
    </div>
  );
}
