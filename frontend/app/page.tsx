import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">🔎 OSINT Platform</h1>
        <p className="mt-3 max-w-md text-slate-400">
          Ochiq manbalardan ma'lumot yig'ish va tahlil qilish uchun web platforma.
        </p>
      </div>
      <div className="flex gap-4">
        <Link
          href="/login"
          className="rounded-lg bg-indigo-600 px-6 py-2.5 font-medium text-white hover:bg-indigo-500"
        >
          Kirish
        </Link>
        <Link
          href="/register"
          className="rounded-lg border border-slate-700 px-6 py-2.5 font-medium hover:bg-slate-800"
        >
          Ro'yxatdan o'tish
        </Link>
      </div>
      <p className="max-w-md text-xs text-slate-600">
        ⚠️ Faqat qonuniy va axloqiy maqsadlar uchun. Faqat ochiq ma'lumotlar.
      </p>
    </main>
  );
}
