"use client";

import SearchModule from "@/components/SearchModule";
import { searchUsername } from "@/lib/api";

export default function UsernameSearchPage() {
  return (
    <SearchModule
      title="Username qidiruv"
      description="Username'ni bir nechta ochiq saytda tekshiradi."
      placeholder="masalan: torvalds"
      search={searchUsername}
    />
  );
}
