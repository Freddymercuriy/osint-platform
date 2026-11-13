"use client";

import { AtSign } from "lucide-react";
import SearchModule from "@/components/SearchModule";
import { searchUsername } from "@/lib/api";

export default function UsernameSearchPage() {
  return (
    <SearchModule
      kind="username"
      icon={AtSign}
      tone="cyan"
      title="Username qidiruv"
      description="Taxallusni 13 ta ochiq saytda bir vaqtda tekshiradi va mavjud profillarni topadi."
      placeholder="masalan: torvalds"
      examples={["torvalds", "durov", "elonmusk"]}
      checks={[
        "13 ta ochiq sayt va platforma",
        "Profil mavjudligi (HTTP javob)",
        "To'g'ridan-to'g'ri profil havolasi",
        "Noaniq javoblarni alohida belgilash",
      ]}
      inputMono
      search={searchUsername}
    />
  );
}
