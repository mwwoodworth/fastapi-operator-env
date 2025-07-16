'use client';
import { motion } from 'framer-motion';
import Link from 'next/link';

export default function HomePage() {
  return (
    <section className="text-center py-20 space-y-6">
      <motion.h2 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="text-4xl font-bold">
        Launch Smarter with BrainStack Studio
      </motion.h2>
      <p className="max-w-xl mx-auto text-lg">
        Build, operate and grow your products using our BrainOps design system and automation templates.
      </p>
      <div className="flex justify-center gap-4">
        <Link href="/products" className="bg-blue-600 text-white px-6 py-3 rounded">Explore Templates</Link>
        <Link href="/contact" className="border border-blue-600 text-blue-600 px-6 py-3 rounded">Get In Touch</Link>
      </div>
    </section>
  );
}
