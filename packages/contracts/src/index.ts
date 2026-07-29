/** Shared API contract types (EP02-01 auth, EP02-02 profile, EP02-03 authorization). */

export type HealthStatus = "ok" | "degraded" | "error";

export interface HealthResponse {
  status: HealthStatus;
}

export interface ServiceInfo {
  service: string;
  status: HealthStatus;
}

/** Stable service identifiers used by clients. */
export const SERVICES = {
  api: "fantappero-api",
  web: "fantappero-web",
  mobile: "fantappero-mobile",
} as const;

export type ServiceId = (typeof SERVICES)[keyof typeof SERVICES];

export interface AuthSessionResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
}

export interface UserPublicResponse {
  id: string;
  email: string;
  email_verified: boolean;
  created_at: string;
}

export interface NotificationPreferences {
  email: boolean;
  push: boolean;
}

export interface UserProfileResponse extends UserPublicResponse {
  display_name: string | null;
  avatar_url: string | null;
  language: string;
  timezone: string;
  notifications: NotificationPreferences;
  policy_consent_at: string | null;
  policy_version: string | null;
}

export interface UpdateProfileRequest {
  display_name?: string;
  language?: string;
  timezone?: string;
  notifications_email?: boolean;
  notifications_push?: boolean;
  accept_policy?: boolean;
  policy_version?: string;
  clear_avatar?: boolean;
}

/** Active policy version clients must send when recording consent. */
export const PROFILE_POLICY_VERSION = "2026-01";

export const SUPPORTED_LANGUAGES = ["it", "en", "es", "fr", "de"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export { DEFAULT_UI_LOCALE, LANGUAGE_LABELS, ui, type UiStrings } from "./i18n.ts";

export interface ApiErrorResponse {
  code: string;
  message: string;
}

export interface MessageResponse {
  message: string;
}

export type PlatformRole = "user" | "operator";

export type LeagueMemberRole = "owner" | "member";

export type LeagueState = "draft" | "active";

export const MIN_LEAGUE_COMPETITIONS = 3;

export interface CompetitionResponse {
  id: string;
  provider_id: number;
  name: string;
  country: string;
}

export interface LeagueCompetitionSummary {
  id: string;
  provider_id: number;
  name: string;
  country: string;
}

export interface LeagueResponse {
  id: string;
  name: string;
  season_year: number;
  state: LeagueState;
  role: LeagueMemberRole | null;
  competitions: LeagueCompetitionSummary[];
}

export interface CreateLeagueRequest {
  name: string;
  season_year: number;
  competition_ids: string[];
}

export interface UpdateLeagueRequest {
  name: string;
}

export type AuthView =
  | "login"
  | "register"
  | "forgot-password"
  | "reset-password"
  | "verify-email"
  | "account"
  | "profile"
  | "privacy"
  | "create-league";

export type AsyncState = "idle" | "loading" | "success" | "error" | "empty";

export interface ExportAccountSection {
  id: string;
  email: string;
  email_verified: boolean;
  created_at: string;
  deleted_at: string | null;
}

export interface ExportProfileSection {
  display_name: string | null;
  language: string;
  timezone: string;
  notifications_email: boolean;
  notifications_push: boolean;
  policy_consent_at: string | null;
  policy_version: string | null;
  avatar_present: boolean;
}

export interface ExportLeagueMembershipSection {
  league_id: string;
  league_name: string;
  role: LeagueMemberRole;
  joined_at: string;
  historical_display_name: string | null;
}

export interface ExportSessionSection {
  id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
}

export interface ExportCompetitiveSummary {
  league_memberships_preserved: number;
  competitive_tables_present: boolean;
}

export interface UserDataExportResponse {
  format_version: string;
  exported_at: string;
  account: ExportAccountSection;
  profile: ExportProfileSection;
  league_memberships: ExportLeagueMembershipSection[];
  sessions: ExportSessionSection[];
  competitive_summary: ExportCompetitiveSummary;
}

export interface DeleteAccountRequest {
  password: string;
  confirm: boolean;
}

export interface DeleteAccountResponse {
  message: string;
}

export interface PrivacyFormState {
  status: AsyncState;
  error?: ApiErrorResponse;
  message?: string;
}

export interface ProfileFormState {
  status: AsyncState;
  error?: ApiErrorResponse;
  message?: string;
}

export interface AuthFormState {
  status: AsyncState;
  error?: ApiErrorResponse;
  message?: string;
}

export interface LeagueFormState {
  status: AsyncState;
  error?: ApiErrorResponse;
  message?: string;
}
