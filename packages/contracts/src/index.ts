/** Shared API contract types (scaffold — OpenAPI generation comes later). */

export {
  hasAnyPermission,
  hasPermissions,
  resolvePermissions,
} from "./auth.js";
export type {
  AuthErrorResponse,
  AuthMessageResponse,
  AuthTokensResponse,
  ForgotPasswordRequest,
  GlobalRole,
  LeagueRole,
  LeagueSummary,
  LoginRequest,
  Permission,
  PermissionContext,
  RefreshRequest,
  RegisterRequest,
  ResendVerificationRequest,
  ResetPasswordRequest,
  SessionUser,
  VerifyEmailRequest,
} from "./auth.js";

export {
  PROFILE_LANGUAGE_OPTIONS,
  PROFILE_TIMEZONE_OPTIONS,
} from "./profile.js";
export type {
  PolicyConsentRequest,
  UpdateProfileRequest,
  UserProfile,
  UserType,
} from "./profile.js";

export {
  DELETE_ACCOUNT_CONFIRMATION_PHRASE,
} from "./privacy.js";
export type {
  AccountDataExport,
  DeleteAccountRequest,
  PrivacyMessageResponse,
} from "./privacy.js";

export type {
  AcceptedLeagueInvite,
  AcceptLeagueInviteRequest,
  CompetitionSummary,
  CreatedLeagueInvite,
  CreateLeagueInviteRequest,
  CreateLeagueRequest,
  FantasyRole,
  LeagueAdminPanel,
  LeagueCalendar,
  LeagueCalendarFormat,
  LeagueCalendarMatchup,
  LeagueCalendarRound,
  LeagueCalendarStatus,
  LeagueDetail,
  LeagueInvite,
  LeagueInviteStatus,
  LeagueLifecycle,
  LeagueLifecycleBlocker,
  LeagueListoneEntry,
  LeagueListoneOverride,
  LeagueListoneRefreshCounters,
  LeagueListoneRefreshResult,
  LeagueMember,
  LeagueRules,
  LeagueRulesOptions,
  LeagueRosterConfig,
  LeagueState,
  TransitionLeagueStateRequest,
  UpdateLeagueRulesRequest,
  CreateNamedLeagueInviteRequest,
  FantasyCoachDirectoryItem,
  NamedLeagueInvite,
  NamedLeagueInviteStatus,
  PaginatedFantasyCoachDirectory,
  RespondedNamedLeagueInvite,
} from "./leagues.js";

export type { BreadcrumbItem, NavItemDefinition, NavSurface } from "./navigation.js";

export {
  ALL_MACROFLOWS,
  WIREFRAME_CATALOG,
  WIREFRAME_STATES,
  getWireframeScreen,
  macroflowsCovered,
  parseWireframeState,
} from "./wireframes.js";
export type {
  Macroflow,
  WireframeScreenId,
  WireframeScreenMeta,
  WireframeUiState,
} from "./wireframes.js";

export {
  SERVICES,
  type HealthResponse,
  type HealthStatus,
  type ServiceId,
  type ServiceInfo,
} from "./health.js";
