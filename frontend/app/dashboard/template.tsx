"use client";

import { PageTransition } from "@/components/motion";

/** template.tsx har sahifa almashganda qayta yaratiladi — kontent yumshoq kirib keladi. */
export default function DashboardTemplate({ children }: { children: React.ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}
