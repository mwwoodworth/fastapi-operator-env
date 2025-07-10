import products from '../../data/products.json';
import Link from 'next/link';

export const metadata = { title: 'Products' };

export default function ProductsPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-semibold">Products</h2>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((p) => (
          <li key={p.id} className="border rounded-lg p-4 flex flex-col">
            <h3 className="text-lg font-semibold mb-2">{p.title}</h3>
            <p className="flex-1">{p.description}</p>
            <Link href={p.link} className="mt-4 underline text-blue-600">{p.cta || 'Learn more'}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
