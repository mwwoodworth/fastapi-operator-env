'use client';
import React, { useEffect, useState } from 'react';

interface Props {
  src: string;
}

export default function MarkdownPreview({ src }: Props) {
  const [content, setContent] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(src);
        const text = await res.text();
        setContent(text);
      } catch (e) {
        console.error(e);
      }
    }
    load();
  }, [src]);

  return (
    <div className="prose max-w-none dark:prose-invert" dangerouslySetInnerHTML={{ __html: markdownToHtml(content) }} />
  );
}

function markdownToHtml(md: string): string {
  return md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')
    .replace(/\*(.*)\*/gim, '<i>$1</i>')
    .replace(/\n$/gim, '<br />');
}
