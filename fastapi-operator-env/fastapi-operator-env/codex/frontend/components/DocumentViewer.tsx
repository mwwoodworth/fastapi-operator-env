import React from 'react';

interface Props {
  content: string;
}

export default function DocumentViewer({ content }: Props) {
  return (
    <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: content }} />
  );
}
