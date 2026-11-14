"use client";

/**
 * Motion design primitivlari (framer-motion).
 * Qoidalar: harakat ma'no tashiydi (kirish, holat o'zgarishi, e'tibor), qisqa (150–600ms),
 * spring fizikasi, `prefers-reduced-motion` hurmat qilinadi (MotionProvider orqali).
 */

import {
  AnimatePresence,
  MotionConfig,
  animate,
  motion,
  useInView,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
  type Variants,
} from "framer-motion";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

export { AnimatePresence, motion };

/** Umumiy "ease-out expo" egri chizig'i va spring sozlamalari */
export const EASE = [0.16, 1, 0.3, 1] as const;
export const SPRING = { type: "spring", stiffness: 380, damping: 30, mass: 0.8 } as const;
export const SPRING_SOFT = { type: "spring", stiffness: 160, damping: 22 } as const;

/* ------------------------------------------------------------------ Provider */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  // reducedMotion="user": OS'da "harakatni kamaytirish" yoqilgan bo'lsa transform animatsiyalari o'chadi
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/* ------------------------------------------------------------------ Reveal */
/** Ko'rinish maydoniga kirganda paydo bo'ladi (bir marta): ko'tarilish + xiralikdan tiniqlashish. */
export function Reveal({
  children,
  delay = 0,
  y = 18,
  className,
  once = true,
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  className?: string;
  once?: boolean;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, margin: "0px 0px -60px 0px" }}
      transition={{ duration: 0.7, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ Stagger */
const staggerParent: Variants = {
  hidden: {},
  show: (stagger: number) => ({ transition: { staggerChildren: stagger, delayChildren: 0.05 } }),
};
const staggerChild: Variants = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.55, ease: EASE } },
};

/** Bolalarini ketma-ket (zinapoya) paydo qiladi. Ichida <StaggerItem> ishlating. */
export function Stagger({
  children,
  className,
  stagger = 0.07,
  inView = true,
}: {
  children: React.ReactNode;
  className?: string;
  stagger?: number;
  inView?: boolean;
}) {
  return (
    <motion.div
      className={className}
      variants={staggerParent}
      custom={stagger}
      initial="hidden"
      {...(inView
        ? { whileInView: "show", viewport: { once: true, margin: "0px 0px -40px 0px" } }
        : { animate: "show" })}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={staggerChild}>
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ CountUp */
/** Raqam 0 dan qiymatgacha "sanab" chiqadi; qiymat o'zgarsa yangisiga silliq o'tadi. */
export function CountUp({ value, duration = 1.1, className }: { value: number; duration?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const mv = useMotionValue(0);
  const [text, setText] = useState("0");

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setText(Math.round(value).toLocaleString("uz-UZ"));
      return;
    }
    const controls = animate(mv, value, {
      duration,
      ease: EASE,
      onUpdate: (v) => setText(Math.round(v).toLocaleString("uz-UZ")),
    });
    return () => controls.stop();
  }, [value, inView, duration, mv, reduce]);

  return (
    <span ref={ref} className={className}>
      {text}
    </span>
  );
}

/* ------------------------------------------------------------------ TextReveal */
/** Sarlavhani so'zma-so'z pastdan ko'tarib chiqaradi. `gradientWords` — gradientli so'zlar indekslari. */
export function TextReveal({
  text,
  className,
  delay = 0,
  gradientWords = [],
}: {
  text: string;
  className?: string;
  delay?: number;
  gradientWords?: number[];
}) {
  const words = text.split(" ");
  return (
    <span className={className} aria-label={text}>
      {words.map((w, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.12em] align-bottom" aria-hidden>
          <motion.span
            className={cn("inline-block", gradientWords.includes(i) && "text-gradient")}
            initial={{ y: "110%", rotate: 4 }}
            animate={{ y: 0, rotate: 0 }}
            transition={{ duration: 0.8, delay: delay + i * 0.07, ease: EASE }}
          >
            {w}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------ ScrambleText */
const GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%&*<>/";

/** "Shifr ochilishi" effekti: belgilar tasodifiy almashib, asl matnga aylanadi. */
export function ScrambleText({ text, className, delay = 0 }: { text: string; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  const [out, setOut] = useState(text);

  useEffect(() => {
    if (reduce) {
      setOut(text);
      return;
    }
    let raf = 0;
    let timer: ReturnType<typeof setTimeout>;
    const duration = Math.min(1100, 350 + text.length * 35); // ms
    let start = 0;
    const tick = (now: number) => {
      if (!start) start = now;
      const progress = Math.min(1, (now - start) / duration);
      const revealed = Math.floor(progress * text.length);
      if (progress >= 1) {
        setOut(text);
        return;
      }
      setOut(
        text
          .split("")
          .map((ch, i) => (i < revealed || ch === " " || ch === "·" ? ch : GLYPHS[Math.floor(Math.random() * GLYPHS.length)]))
          .join(""),
      );
      raf = requestAnimationFrame(tick);
    };
    setOut(text.replace(/[^ ·]/g, "•"));
    timer = setTimeout(() => (raf = requestAnimationFrame(tick)), delay * 1000);
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
    };
  }, [text, delay, reduce]);

  return (
    <span className={className} aria-label={text}>
      {out}
    </span>
  );
}

/* ------------------------------------------------------------------ Tilt */
/** Sichqoncha ostida 3D egiladigan konteyner (landing kartalari uchun). */
export function Tilt({ children, className, max = 7 }: { children: React.ReactNode; className?: string; max?: number }) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rx = useSpring(useTransform(y, [-0.5, 0.5], [max, -max]), { stiffness: 200, damping: 20 });
  const ry = useSpring(useTransform(x, [-0.5, 0.5], [-max, max]), { stiffness: 200, damping: 20 });

  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      style={{ rotateX: rx, rotateY: ry, transformPerspective: 900, transformStyle: "preserve-3d" }}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        x.set((e.clientX - r.left) / r.width - 0.5);
        y.set((e.clientY - r.top) / r.height - 0.5);
      }}
      onMouseLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ Magnetic */
/** Sichqonchaga biroz "tortiladigan" element (asosiy CTA tugmalari uchun). */
export function Magnetic({ children, strength = 0.25 }: { children: React.ReactNode; strength?: number }) {
  const reduce = useReducedMotion();
  const x = useSpring(0, { stiffness: 250, damping: 18 });
  const y = useSpring(0, { stiffness: 250, damping: 18 });
  if (reduce) return <>{children}</>;
  return (
    <motion.span
      className="inline-block"
      style={{ x, y }}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        x.set((e.clientX - (r.left + r.width / 2)) * strength);
        y.set((e.clientY - (r.top + r.height / 2)) * strength);
      }}
      onMouseLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.span>
  );
}

/* ------------------------------------------------------------------ PageTransition */
/** Sahifa almashganda kontent yumshoq kirib keladi (dashboard/template.tsx ichida). */
export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ RouteProgress */
/** Sahifa almashganda tepada gradient chiziq yugurib o'tadi. */
export function RouteProgress() {
  const pathname = usePathname();
  const [key, setKey] = useState(0);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setKey((k) => k + 1);
  }, [pathname]);

  return (
    <AnimatePresence>
      {key > 0 && (
        <motion.div
          key={key}
          className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-[2px] origin-left bg-brand-gradient shadow-[0_0_12px_rgba(34,211,238,.8)]"
          initial={{ scaleX: 0, opacity: 1 }}
          animate={{ scaleX: 1, opacity: [1, 1, 0] }}
          transition={{ duration: 0.7, ease: EASE, times: [0, 0.7, 1] }}
        />
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ Aurora */
/** Fon ortidagi sekin suzib yuruvchi rangli nur dog'lari (butun ilova uchun). */
export function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden print:hidden">
      <div className="aurora-blob left-[-10%] top-[-15%] h-[42rem] w-[42rem] text-cyan-500/[0.16] [animation-duration:26s]" />
      <div className="aurora-blob right-[-12%] top-[5%] h-[38rem] w-[38rem] text-violet-600/[0.20] [animation-delay:-8s] [animation-duration:32s]" />
      <div className="aurora-blob bottom-[-20%] left-[30%] h-[36rem] w-[36rem] text-fuchsia-600/[0.11] [animation-delay:-15s] [animation-duration:38s]" />
    </div>
  );
}

/* ------------------------------------------------------------------ Parallax blip */
/** Yengil "suzish" — bezak elementlari uchun. */
export function Float({
  children,
  className,
  amplitude = 8,
  duration = 6,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  amplitude?: number;
  duration?: number;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      animate={{ y: [0, -amplitude, 0] }}
      transition={{ duration, delay, repeat: Infinity, ease: "easeInOut" }}
    >
      {children}
    </motion.div>
  );
}
