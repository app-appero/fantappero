import type {
  AuthMessageResponse,
  AuthTokensResponse,
  ForgotPasswordRequest,
  LoginRequest,
  RefreshRequest,
  RegisterRequest,
  ResetPasswordRequest,
  SessionUser,
  VerifyEmailRequest,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export function register(body: RegisterRequest): Promise<AuthMessageResponse> {
  return apiRequest<AuthMessageResponse>("/auth/register", { body });
}

export function login(body: LoginRequest): Promise<AuthTokensResponse> {
  return apiRequest<AuthTokensResponse>("/auth/login", { body });
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
