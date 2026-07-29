import type {
  ApiErrorResponse,
  AuthSessionResponse,
  DeleteAccountRequest,
  DeleteAccountResponse,
  MessageResponse,
  UpdateProfileRequest,
  UserDataExportResponse,
  UserProfileResponse,
} from "@fantappero/contracts";

export class AuthApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, body: ApiErrorResponse) {
    super(body.message);
    this.name = "AuthApiError";
    this.code = body.code;
    this.status = status;
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}

async function request<T>(
  baseUrl: string,
  path: string,
  init: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const body = await parseJson<ApiErrorResponse>(response);
    throw new AuthApiError(response.status, {
      code: body.code ?? "unknown_error",
      message: body.message ?? "Request failed.",
    });
  }

  return parseJson<T>(response);
}

export function createAuthClient(baseUrl: string) {
  return {
    register(email: string, password: string) {
      return request<AuthSessionResponse>(baseUrl, "/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
    },
    login(email: string, password: string) {
      return request<AuthSessionResponse>(baseUrl, "/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
    },
    logout(token: string) {
      return request<MessageResponse>(baseUrl, "/auth/logout", { method: "POST" }, token);
    },
    me(token: string) {
      return request<UserProfileResponse>(baseUrl, "/auth/me", {}, token);
    },
    updateProfile(token: string, body: UpdateProfileRequest) {
      return request<UserProfileResponse>(
        baseUrl,
        "/users/me",
        { method: "PATCH", body: JSON.stringify(body) },
        token,
      );
    },
    uploadAvatar(token: string, formData: FormData) {
      return request<UserProfileResponse>(
        baseUrl,
        "/users/me/avatar",
        { method: "POST", body: formData },
        token,
      );
    },
    exportData(token: string) {
      return request<UserDataExportResponse>(baseUrl, "/users/me/export", {}, token);
    },
    deleteAccount(token: string, body: DeleteAccountRequest) {
      return request<DeleteAccountResponse>(
        baseUrl,
        "/users/me/delete",
        { method: "POST", body: JSON.stringify(body) },
        token,
      );
    },
  };
}

export type AuthClient = ReturnType<typeof createAuthClient>;
