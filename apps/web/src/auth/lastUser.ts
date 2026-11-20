/** Ultimo account che ha fatto accesso su questo dispositivo (nome ed email, nessun segreto). */

import { avatarInitials } from "@fantappero/contracts";

const LAST_USER_KEY = "fantappero.lastUser";

export type LastUser = {
  displayName: string;
  email: string;
};

export function readLastUser(): LastUser | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  try {
    const raw = localStorage.getItem(LAST_USER_KEY);
    if (!raw) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof (parsed as LastUser).displayName === "string" &&
      typeof (parsed as LastUser).email === "string" &&
      (parsed as LastUser).displayName.trim() &&
      (parsed as LastUser).email.trim()
    ) {
      return parsed as LastUser;
    }
  } catch {
    // dati rovinati: si riparte dal modulo normale
  }
  return null;
}

export function writeLastUser(user: LastUser): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    localStorage.setItem(LAST_USER_KEY, JSON.stringify(user));
  } catch {
    // storage pieno o bloccato: il ricordo dell'account è solo una comodità
  }
}

export function clearLastUser(): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    localStorage.removeItem(LAST_USER_KEY);
  } catch {
    // vedi sopra
  }
}

/** Iniziali per l'avatar (prima e ultima parola; un'emoji resta intera). */
export function initialsOf(displayName: string): string {
  return avatarInitials(displayName, { words: "first-last" });
}
