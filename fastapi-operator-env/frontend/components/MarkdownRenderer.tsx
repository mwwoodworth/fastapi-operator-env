'use client';
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={`prose prose-lg dark:prose-invert max-w-none ${className}`}
      components={{
        h1: ({ children }) => (
          <h1 className="text-3xl font-bold mt-8 mb-4 text-gray-900 dark:text-gray-100">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-2xl font-semibold mt-6 mb-3 text-gray-800 dark:text-gray-200">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-xl font-medium mt-4 mb-2 text-gray-700 dark:text-gray-300">{children}</h3>
        ),
        p: ({ children }) => (
          <p className="mb-4 text-gray-600 dark:text-gray-400 leading-relaxed">{children}</p>
        ),
        ul: ({ children }) => (
          <ul className="list-disc list-inside mb-4 text-gray-600 dark:text-gray-400">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal list-inside mb-4 text-gray-600 dark:text-gray-400">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="mb-1">{children}</li>
        ),
        code: ({ inline, children }) => 
          inline ? (
            <code className="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded text-sm text-purple-600 dark:text-purple-400">
              {children}
            </code>
          ) : (
            <code className="block bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto text-sm">
              {children}
            </code>
          ),
        pre: ({ children }) => (
          <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto mb-4">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-purple-500 pl-4 italic my-4 text-gray-600 dark:text-gray-400">
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            {children}
          </a>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto mb-4">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-gray-50 dark:bg-gray-800">{children}</thead>
        ),
        tbody: ({ children }) => (
          <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
            {children}
          </tbody>
        ),
        th: ({ children }) => (
          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
            {children}
          </td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}