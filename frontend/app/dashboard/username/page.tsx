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
      title="Telegram username"
      description="Telegram akkauntini username yoki ID bo'yicha tekshiradi: ID, usernamelar, username o'zgarishlari va siz bilan umumiy guruhlar."
      placeholder="masalan: @botfather, t.me/telegram yoki 93372553"
      examples={["botfather", "telegram", "93372553"]}
      checks={[
        "Akkaunt ID'si, turi va belgilar (bot, premium, scam)",
        "Faol usernamelar, bio, shaxsiy kanal",
        "Username tarixi — platforma har qidiruvda yozib boradi",
        "Umumiy guruhlar va ulardagi xabarlar soni",
      ]}
      inputMono
      search={searchUsername}
    />
  );
}
