import '../styles/globals.css';
import Link from 'next/link';

export const metadata = {
  title: 'BrainStack Studio',
  description: 'BrainOps templates, guides and automation tools',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const year = new Date().getFullYear();
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="flex justify-between items-center p-4 border-b">
          <Link href="/" className="font-bold text-xl">BrainStackStudio</Link>
          <nav className="space-x-4">
            <Link href="/products">Products</Link>
            <Link href="/about">About</Link>
            <Link href="/blog">Blog</Link>
            <Link href="/contact">Contact</Link>
            <Link href="/dashboard" className="font-semibold">Dashboard</Link>
          </nav>
        </header>
        <main className="flex-1 p-4">{children}</main>
        <footer className="border-t p-4 text-center text-sm">&copy; {year} BrainStackStudio</footer>
      </body>
    </html>
  );
}
