'use client';
import React, { useEffect, useState } from 'react';
import { fetchProductDocs } from '../utils/api';

export default function ProductTable() {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetchProductDocs();
        setDocs(res.entries || res.documents || res);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-2">
      {loading && <p>Loading...</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th className="p-1">Title</th>
            <th className="p-1">Date</th>
            <th className="p-1">Actions</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d: any) => (
            <tr key={d.id} className="border-t">
              <td className="p-1">{d.title}</td>
              <td className="p-1">{d.timestamp?.split('T')[0]}</td>
              <td className="p-1">
                <button className="underline text-xs">Export</button>
                <button className="underline text-xs ml-2">Upload to Gumroad</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
