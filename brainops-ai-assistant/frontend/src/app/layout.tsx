import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { PWAInit } from "@/components/pwa-init";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "BrainOps AI Assistant",
  description: "AI Chief of Staff - Full Operational Control",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "BrainOps",
  },
};

export const viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#0f172a" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className={inter.className}>
        <Providers>
          <PWAInit />
          {children}
        </Providers>
      </body>
    </html>
  );
}