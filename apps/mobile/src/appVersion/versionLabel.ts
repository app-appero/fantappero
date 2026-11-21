/**
 * Versione dell'app come la vedono gli operatori nelle segnalazioni: «1.2.0 (3)», cioè
 * versionName e versionCode di `app.json`. Solo logica pura: gira nei test `node:test`.
 */
export function appVersionLabel(
  versionName: string | null | undefined,
  versionCode: number | null | undefined,
): string | undefined {
  const name = (versionName ?? "").trim();
  const code =
    typeof versionCode === "number" && Number.isSafeInteger(versionCode) && versionCode > 0
      ? versionCode
      : null;
  if (name && code !== null) {
    return `${name} (${code})`;
  }
  if (name) {
    return name;
  }
  return code !== null ? `(${code})` : undefined;
}
