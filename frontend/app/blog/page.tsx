import fs from 'fs';
import path from 'path';
import { marked } from 'marked';

export const metadata = { title: 'Blog' };

export default function BlogPage() {
  const postsDir = path.join(process.cwd(), 'dashboard_ui/data/posts');
  const files = fs.readdirSync(postsDir);
  const posts = files.map((file) => {
    const md = fs.readFileSync(path.join(postsDir, file), 'utf8');
    const html = marked(md);
    return { slug: file.replace(/\.md$/, ''), html };
  });

  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-semibold">Blog</h2>
      {posts.map((p) => (
        <article key={p.slug} className="prose" dangerouslySetInnerHTML={{ __html: p.html }} />
      ))}
    </div>
  );
}
