"use client";

/** Harakat — faqat qisqa paydo bo'lish (fade). Bezak effektlari dizayn tizimiga ko'ra ishlatilmaydi. */
export function PageTransition({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-in">{children}</div>;
}
