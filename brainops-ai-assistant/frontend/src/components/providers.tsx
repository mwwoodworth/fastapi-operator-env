"use client";

import { ReactNode } from "react";
import { Toaster } from "react-hot-toast";
import { SWRConfig } from "swr";
import ServiceWorkerRegistration from "./ServiceWorkerRegistration";
import OfflineStatus from "./OfflineStatus";

// API client configuration
const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher,
        revalidateOnFocus: false,
        errorRetryCount: 3,
        errorRetryInterval: 1000,
      }}
    >
      <ServiceWorkerRegistration />
      <div className="relative">
        <OfflineStatus className="fixed top-4 right-4 z-50" />
        {children}
      </div>
      <Toaster
        position="top-right"
        toastOptions={{
          className: "glass-card",
          style: {
            background: "rgba(255, 255, 255, 0.1)",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            backdropFilter: "blur(12px)",
            color: "white",
            marginTop: "60px", // Space for offline status
          },
        }}
      />
    </SWRConfig>
  );
}