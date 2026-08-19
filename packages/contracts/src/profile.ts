/** Profile and preferences contracts (EP02-02). */

/** Full profile snapshot for the authenticated user. */
export interface UserProfile {
  email: string;
  displayName: string;
  avatarUrl: string | null;
  language: string;
  timezone: string;
  notificationsEmail: boolean;
  notificationsPush: boolean;
  /** Local hour (0-23) window during which email/push are deferred; null = disabled. */
  quietHoursStartHour: number | null;
  quietHoursEndHour: number | null;
  policyConsentAt: string | null;
  policyVersion: string | null;
  currentPolicyVersion: string;
  userType: UserType;
  availableForInvites: boolean;
}

export type UserType = "human" | "ai";

export interface UpdateProfileRequest {
  displayName?: string;
  language?: string;
  timezone?: string;
  notificationsEmail?: boolean;
  notificationsPush?: boolean;
  quietHoursStartHour?: number | null;
  quietHoursEndHour?: number | null;
  availableForInvites?: boolean;
}

export interface PolicyConsentRequest {
  policyVersion: string;
  accepted: boolean;
}

/** Supported UI language options (i18n-ready). */
export const PROFILE_LANGUAGE_OPTIONS = [{ value: "it", label: "Italiano" }] as const;

/** Common timezone options for profile preferences. */
export const PROFILE_TIMEZONE_OPTIONS = [
  { value: "Europe/Rome", label: "Europa/Roma (UTC+1/+2)" },
  { value: "Europe/London", label: "Europa/Londra (UTC+0/+1)" },
  { value: "Europe/Berlin", label: "Europa/Berlino (UTC+1/+2)" },
  { value: "Europe/Paris", label: "Europa/Parigi (UTC+1/+2)" },
] as const;
