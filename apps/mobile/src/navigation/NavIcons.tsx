import Feather from "@expo/vector-icons/Feather";
import type { ComponentProps } from "react";

export type NavIconProps = {
  color: string;
  size?: number;
};

type FeatherName = ComponentProps<typeof Feather>["name"];

export const NAV_ICON_MAP: Record<string, FeatherName> = {
  leagues: "award",
  "league-home": "home",
  "manager-directory": "users",
  "received-invites": "mail",
  matchday: "calendar",
  standings: "bar-chart-2",
  roster: "users",
  formation: "grid",
  auction: "shopping-cart",
  market: "repeat",
  profile: "user",
  more: "menu",
  "league-admin": "shield",
  "admin-home": "shield",
  "admin-leagues": "layers",
  "admin-users": "users",
};

export function NavIcon({ id, color, size = 22 }: { id: string; color: string; size?: number }) {
  const name = NAV_ICON_MAP[id];
  if (!name) {
    return null;
  }
  return <Feather name={name} size={size} color={color} />;
}
