'use client';
import { useRouter } from 'next/navigation';
import { useEffect, useState, ReactNode } from 'react';
import { getSupabase } from '../utils/auth';

export default function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function check() {
      const supabase = getSupabase();
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.push('/');
      } else {
        setChecking(false);
      }
    }
    check();
  }, [router]);

  if (checking) return null;
  return <>{children}</>;
}
