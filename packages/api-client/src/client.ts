/**
 * Platform-agnostic HTTP client core shared by the web and mobile API layers.
 *
 * This module owns everything that is identical between platforms: request
 * construction, header/auth handling, response parsing, FastAPI error body
 * parsing (both the plain-string and the validation-array `detail` shapes),
 * and file upload plumbing.
 *
 * Platform-specific behaviour is injected via `createApiClient(config)`:
 *  - `resolveBaseUrl`: how to read the API base URL (Vite env on web, Expo
 *    public env on mobile). May throw — the error propagates unchanged to
 *    the `apiRequest`/`apiUpload` caller.
 *  - `isDev`: gates diagnostic `console.error` calls (e.g. React Native's
 *    `__DEV__` global on mobile; web opts out by leaving this unset).
 *  - `buildUploadValue`: converts a platform file reference (a DOM `File` on
 *    web, `{ uri, name, type }` on mobile) into a value `FormData.append`
 *    accepts.
 *  - the `*Message` hooks let each platform keep its own user-facing copy
 *    for network/parsing failures.
 */

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

export type ApiRequestOptions = {
  method?: string;
  body?: unknown;
  accessToken?: string | null;
};

export type FastApiErrorBody = {
  message?: string;
  code?: string;
  detail?: string | Array<{ msg?: string }>;
};

export type UploadOptions<TFile> = {
  accessToken: string;
  file: TFile;
  fieldName?: string;
};

export type ApiClientConfig<TFile = unknown> = {
  /** Resolve the current API base URL. May throw; the error propagates as-is. */
  resolveBaseUrl: () => string;
  /** Returns true when diagnostics should be logged to the console. Defaults to always false. */
  isDev?: () => boolean;
  /** Turn a platform file reference into a value `FormData.append` accepts. */
  buildUploadValue: (file: TFile) => string | Blob;
  /** Message used when `fetch` itself rejects (offline/DNS/etc). */
  networkErrorMessage?: (baseUrl: string) => string;
  /** Message used when the response body cannot be parsed as JSON. */
  invalidResponseMessage?: (status: number) => string;
  /** Optional override for FastAPI's plain-text "Not Found" detail (e.g. wrong base URL/port). */
  notFoundMessage?: (status: number) => string;
  /** Fallback message when the error body carries neither `message` nor `detail`. */
  defaultErrorMessage?: (status: number) => string;
};

type ResolvedMessages = {
  networkErrorMessage: (baseUrl: string) => string;
  invalidResponseMessage: (status: number) => string;
  notFoundMessage?: (status: number) => string;
  defaultErrorMessage: (status: number) => string;
};

function extractErrorMessage(
  payload: FastApiErrorBody,
  status: number,
  messages: ResolvedMessages,
): string {
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    if (payload.detail === "Not Found" && messages.notFoundMessage) {
      return messages.notFoundMessage(status);
    }
    return payload.detail;
  }
  if (Array.isArray(payload.detail) && payload.detail.length > 0) {
    const first = payload.detail[0]?.msg;
    if (first) {
      return first;
    }
  }
  return messages.defaultErrorMessage(status);
}

export function createApiClient<TFile = unknown>(config: ApiClientConfig<TFile>) {
  const isDev = config.isDev ?? (() => false);
  const messages: ResolvedMessages = {
    networkErrorMessage:
      config.networkErrorMessage ??
      ((baseUrl: string) => `Connessione non disponibile verso ${baseUrl}.`),
    invalidResponseMessage:
      config.invalidResponseMessage ??
      ((status: number) => `Risposta non valida dall'API (HTTP ${status}).`),
    notFoundMessage: config.notFoundMessage,
    defaultErrorMessage:
      config.defaultErrorMessage ??
      ((status: number) => `Si è verificato un errore (HTTP ${status}).`),
  };

  async function performFetch(url: string, baseUrl: string, init: RequestInit): Promise<Response> {
    try {
      return await fetch(url, init);
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (isDev()) {
        console.error("[api] network error", { url, error });
      }
      throw new ApiError(messages.networkErrorMessage(baseUrl), 0, "network_error");
    }
  }

  async function parseJsonBody<T>(response: Response, url: string): Promise<FastApiErrorBody | T> {
    try {
      return (await response.json()) as FastApiErrorBody | T;
    } catch (parseError) {
      if (isDev()) {
        console.error("[api] non-JSON response", { url, status: response.status, parseError });
      }
      throw new ApiError(
        messages.invalidResponseMessage(response.status),
        response.status,
        "invalid_response",
      );
    }
  }

  function raiseRequestFailed(url: string, response: Response, payload: FastApiErrorBody): never {
    const message = extractErrorMessage(payload, response.status, messages);
    if (isDev()) {
      console.error("[api] request failed", {
        url,
        status: response.status,
        code: payload.code,
        body: payload,
      });
    }
    throw new ApiError(message, response.status, payload.code ?? "unknown_error");
  }

  async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    const baseUrl = config.resolveBaseUrl();
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

    const response = await performFetch(url, baseUrl, {
      method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });

    if (response.status === 204) {
      return undefined as T;
    }

    const payload = await parseJsonBody<T>(response, url);
    if (!response.ok) {
      raiseRequestFailed(url, response, payload as FastApiErrorBody);
    }
    return payload as T;
  }

  async function apiUpload<T>(path: string, options: UploadOptions<TFile>): Promise<T> {
    const baseUrl = config.resolveBaseUrl();
    const url = `${baseUrl}${path}`;
    const formData = new FormData();
    formData.append(options.fieldName ?? "file", config.buildUploadValue(options.file));

    const response = await performFetch(url, baseUrl, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${options.accessToken}`,
      },
      body: formData,
    });

    const payload = await parseJsonBody<T>(response, url);
    if (!response.ok) {
      raiseRequestFailed(url, response, payload as FastApiErrorBody);
    }
    return payload as T;
  }

  return { apiRequest, apiUpload };
}
