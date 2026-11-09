import type {
  AuthMessageResponse,
  AuthOptions,
  AuthTokensResponse,
  ForgotPasswordRequest,
  GoogleHandoffStartResponse,
  GoogleLoginRequest,
  LoginRequest,
  RefreshRequest,
  RegisterRequest,
  ResendVerificationRequest,
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

/**
 * Mobile handoff page only: exchanges the Google ID token for a real session right here, in
 * the browser, and gets back a one-time code to hand the app instead of a token (see
 * `auth.mobile_handoff` on the backend for why).
 */
export function startGoogleHandoff(
  body: GoogleLoginRequest,
): Promise<GoogleHandoffStartResponse> {
  return apiRequest<GoogleHandoffStartResponse>("/auth/google/handoff", { body });
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

export function verifyEmail(body: VerifyEmailRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/verify-email", { body });
}

export function resendVerification(body: ResendVerificationRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/resend-verification", { body });
}

export function forgotPassword(body: ForgotPasswordRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/forgot-password", { body });
}

export function resetPassword(body: ResetPasswordRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/reset-password", { body });
}
