import type { AuthErrorResponse } from "@fantappero/contracts";
import { getWebEnv } from "../config/env";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  accessToken?: string | null;
};

type UploadOptions = {
  accessToken: string;
  file: File;
  fieldName?: string;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { viteApiBaseUrl } = getWebEnv();
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.accessToken) {
    headers.Authorization = `Bearer ${options.accessToken}`;
  }

  const response = await fetch(`${viteApiBaseUrl}${path}`, {
    method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = (await response.json()) as T | AuthErrorResponse;
  if (!response.ok) {
    const errorPayload = payload as AuthErrorResponse;
    throw new ApiError(
      errorPayload.message ?? "Si è verificato un errore.",
      response.status,
      errorPayload.code ?? "unknown_error",
    );
  }
  return payload as T;
}

export async function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  const { viteApiBaseUrl } = getWebEnv();
  const formData = new FormData();
  formData.append(options.fieldName ?? "file", options.file);

  const response = await fetch(`${viteApiBaseUrl}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${options.accessToken}`,
    },
    body: formData,
  });

  const payload = (await response.json()) as T | AuthErrorResponse;
  if (!response.ok) {
    const errorPayload = payload as AuthErrorResponse;
    throw new ApiError(
      errorPayload.message ?? "Si è verificato un errore.",
      response.status,
      errorPayload.code ?? "unknown_error",
    );
  }
  return payload as T;
}
