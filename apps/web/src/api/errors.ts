import type { UiStrings } from "@fantappero/contracts";

/** Map stable API error codes to localized UI copy. */
export function mapApiErrorMessage(
  copy: UiStrings,
  code: string,
  fallback: string,
): string {
  switch (code) {
    case "email_not_verified":
      return copy.errorEmailNotVerified;
    case "forbidden":
      return copy.errorForbidden;
    case "league_validation_error":
      return copy.errorLeagueValidation;
    default:
      return fallback;
  }
}
