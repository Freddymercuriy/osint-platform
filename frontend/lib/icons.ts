import {
  AlertTriangle, Banknote, Bitcoin, Bug, CircleDashed, Cloud, CreditCard, DatabaseZap, Eye, FileWarning, Fingerprint,
  Fish, Flag, FlaskConical, Gavel, Globe, KeyRound, Landmark, Lock, Mail, Megaphone, Network, Radio, ServerCrash,
  Shield, ShieldAlert, ShoppingCart, Siren, Skull, Smartphone, Tag, Target, UserX, Wifi, Zap, type LucideIcon,
} from "lucide-react";

/** Kategoriya ikonlari (admin tanlay oladigan to'plam; nom — `categories.icon`). Butun lucide yuklanmaydi. */
export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  AlertTriangle, Banknote, Bitcoin, Bug, CircleDashed, Cloud, CreditCard, DatabaseZap, Eye, FileWarning, Fingerprint,
  Fish, Flag, FlaskConical, Gavel, Globe, KeyRound, Landmark, Lock, Mail, Megaphone, Network, Radio, ServerCrash,
  Shield, ShieldAlert, ShoppingCart, Siren, Skull, Smartphone, Tag, Target, UserX, Wifi, Zap,
};

export function categoryIcon(name: string | null | undefined): LucideIcon {
  return (name && CATEGORY_ICONS[name]) || Tag;
}
