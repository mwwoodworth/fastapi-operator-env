import '../styles/globals.css';
import { useEffect, useState } from 'react';
import Head from 'next/head';

export default function App({ Component, pageProps }) {
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    const stored = localStorage.getItem('theme');
    if (stored) setTheme(stored);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  return (
    <>
      <Head>
        <title>BrainOps Dashboard</title>
        <link rel="icon" href="/favicon.svg" />
      </Head>
      <Component {...pageProps} theme={theme} setTheme={setTheme} />
    </>
  );
}
