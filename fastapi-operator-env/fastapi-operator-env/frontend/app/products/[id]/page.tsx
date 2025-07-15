import fs from 'fs';
import path from 'path';
import products from '../../../data/products.json';
import { marked } from 'marked';

interface Params { params: { id: string } }

export function generateMetadata({ params }: Params) {
  const product = products.find(p => p.id === params.id);
  return { title: product ? product.title : 'Product' };
}

export function generateStaticParams() {
  return products.map(p => ({ id: p.id }));
}

export default function ProductDetailPage({ params }: Params) {
  const product = products.find(p => p.id === params.id);
  if (!product) return <p>Product not found</p>;
  const docPath = path.join(process.cwd(), 'dashboard_ui/data/product_docs', `${params.id}.md`);
  let docHtml = '';
  if (fs.existsSync(docPath)) {
    const md = fs.readFileSync(docPath, 'utf8');
    docHtml = marked(md);
  }
  return (
    <div className="space-y-4 max-w-2xl">
      <h2 className="text-3xl font-semibold">{product.title}</h2>
      <p>{product.description}</p>
      {product.link && (
        <a href={product.link} className="inline-block mt-2 px-4 py-2 bg-blue-600 text-white rounded" target="_blank" rel="noopener noreferrer">{product.cta || 'Buy'}</a>
      )}
      {docHtml && <article className="prose" dangerouslySetInnerHTML={{ __html: docHtml }} />}
    </div>
  );
}
