import type { AuthErrorResponse } from "@fantappero/contracts";
import { loadMobileEnv, MobileEnvError } from "../config/env";

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

type FastApiErrorBody = AuthErrorResponse & {
  detail?: string | Array<{ msg?: string }>;
};

function resolveApiBaseUrl(): string {
  try {
    return loadMobileEnv().expoPublicApiBaseUrl;
  } catch (error) {
    if (error instanceof MobileEnvError) {
      throw new ApiError(
        "URL API non configurato. Imposta EXPO_PUBLIC_API_BASE_URL.",
        0,
        "missing_api_base_url",
      );
    }
    throw error;
  }
}

function extractErrorMessage(payload: FastApiErrorBody, status: number): string {
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    if (payload.detail === "Not Found") {
      return `Endpoint non trovato (${status}). Controlla EXPO_PUBLIC_API_BASE_URL (API su porta 8001).`;
    }
    return payload.detail;
  }
  if (Array.isArray(payload.detail) && payload.detail.length > 0) {
    const first = payload.detail[0]?.msg;
    if (first) {
      return first;
    }
  }
  return `Si è verificato un errore (HTTP ${status}).`;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = resolveApiBaseUrl();
  const url = `${baseUrl}${path}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.accessToken) {
    headers.Authorization = `Bearer ${options.accessToken}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (__DEV__) {
      console.error("[api] network error", { url, error });
    }
    throw new ApiError(
      `Connessione non disponibile verso ${baseUrl}. Verifica rete e EXPO_PUBLIC_API_BASE_URL.`,
      0,
      "network_error",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let payload: FastApiErrorBody | T;
  try {
    payload = (await response.json()) as FastApiErrorBody | T;
  } catch (parseError) {
    if (__DEV__) {
      console.error("[api] non-JSON response", { url, status: response.status, parseError });
    }
    throw new ApiError(
      `Risposta non valida dall'API (HTTP ${response.status}). Controlla EXPO_PUBLIC_API_BASE_URL.`,
      response.status,
      "invalid_response",
    );
  }

  if (!response.ok) {
    const errorPayload = payload as FastApiErrorBody;
    const message = extractErrorMessage(errorPayload, response.status);
    if (__DEV__) {
      console.error("[api] request failed", {
        url,
        status: response.status,
        code: errorPayload.code,
        body: errorPayload,
      });
    }
    throw new ApiError(message, response.status, errorPayload.code ?? "unknown_error");
  }
  return payload as T;
}

type UploadOptions = {
  accessToken: string;
  file: { uri: string; name: string; type?: string };
  fieldName?: string;
};

export async function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  const baseUrl = resolveApiBaseUrl();
  const url = `${baseUrl}${path}`;
  const formData = new FormData();
  formData.append(options.fieldName ?? "file", {
    uri: options.file.uri,
    name: options.file.name,
    type: options.file.type ?? "text/csv",
  } as unknown as Blob);

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${options.accessToken}`,
      },
      body: formData,
    });
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      `Connessione non disponibile verso ${baseUrl}. Verifica rete e EXPO_PUBLIC_API_BASE_URL.`,
      0,
      "network_error",
    );
  }

  let payload: FastApiErrorBody | T;
  try {
    payload = (await response.json()) as FastApiErrorBody | T;
  } catch {
    throw new ApiError(
      `Risposta non valida dall'API (HTTP ${response.status}).`,
      response.status,
      "invalid_response",
    );
  }

  if (!response.ok) {
    const errorPayload = payload as FastApiErrorBody;
    throw new ApiError(
      extractErrorMessage(errorPayload, response.status),
      response.status,
      errorPayload.code ?? "unknown_error",
    );
  }
  return payload as T;
}
