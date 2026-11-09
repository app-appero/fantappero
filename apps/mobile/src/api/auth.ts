import type {
  AuthMessageResponse,
  AuthOptions,
  AuthTokensResponse,
  ForgotPasswordRequest,
  GoogleHandoffClaimRequest,
  GoogleLoginRequest,
  LoginRequest,
  RefreshRequest,
  RegisterRequest,
  ResetPasswordRequest,
  SessionUser,
  VerifyEmailRequest,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

/** Cosa è attivo per accedere/registrarsi (pubblico, senza token). */
export function fetchAuthOptions(): Promise<AuthOptions> {
  return apiRequest<AuthOptions>("/auth/options", { method: "GET" });
}

export function register(body: RegisterRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/register", { body });
}

export function login(body: LoginRequest): Promise<AuthTokensResponse> {
  return apiRequest<AuthTokensResponse>("/auth/login", { body });
}

export function loginWithGoogle(body: GoogleLoginRequest): Promise<AuthTokensResponse> {
  return apiRequest<AuthTokensResponse>("/auth/google", { body });
}

/** Claims the session the web handoff page already created from the one-time pickup code. */
export function claimGoogleHandoff(body: GoogleHandoffClaimRequest): Promise<AuthTokensResponse> {
  return apiRequest<AuthTokensResponse>("/auth/google/handoff/claim", { body });
}

export function refresh(body: RefreshRequest): Promise<AuthTokensResponse> {
  return apiRequest<AuthTokensResponse>("/auth/refresh", { body });
}

export function logout(body: RefreshRequest): Promise<void> {
  return apiRequest<void>("/auth/logout", { body });
}

export function fetchMe(accessToken: string): Promise<SessionUser> {
  return apiRequest<SessionUser>("/auth/me", { accessToken });
}

export function forgotPassword(body: ForgotPasswordRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/forgot-password", { body });
}

export function resetPassword(body: ResetPasswordRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/reset-password", { body });
}

export function verifyEmail(body: VerifyEmailRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/verify-email", { body });
}
