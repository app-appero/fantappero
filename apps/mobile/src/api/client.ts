import {
  createApiClient,
  ApiError,
  getApiErrorMessage,
  type UnauthorizedRecovery,
} from "@fantappero/api-client";
import { loadMobileEnv, MobileEnvError } from "../config/env";

export { ApiError, getApiErrorMessage };

let recoverUnauthorized: UnauthorizedRecovery | null = null;

/** Registered by the session provider so a 401 renews the access token once. */
export function setUnauthorizedRecovery(next: UnauthorizedRecovery | null): void {
  recoverUnauthorized = next;
}

type UploadFile = { uri: string; name: string; type?: string };

type UploadOptions = {
  accessToken: string;
  file: UploadFile;
  fieldName?: string;
};

function resolveApiBaseUrl(): string {
  try {
    return loadMobileEnv().expoPublicApiBaseUrl;
  } catch (error) {
    if (error instanceof MobileEnvError) {
      throw new ApiError(
        "Servizio non disponibile. Riprova tra poco.",
        0,
        "missing_api_base_url",
      );
    }
    throw error;
  }
}

const client = createApiClient<UploadFile>({
  resolveBaseUrl: resolveApiBaseUrl,
  isDev: () => __DEV__,
  recoverUnauthorized: (input) => {
    if (!recoverUnauthorized) {
      throw input.error;
    }
    return recoverUnauthorized(input);
  },
  buildUploadValue: (file) =>
    ({
      uri: file.uri,
      name: file.name,
      type: file.type ?? "text/csv",
    }) as unknown as Blob,
  networkErrorMessage: () => "Connessione non disponibile. Riprova tra poco.",
  invalidResponseMessage: () => "Risposta non valida. Riprova tra poco.",
  notFoundMessage: () => "Risorsa non trovata. Riprova tra poco.",
});

export const apiRequest = client.apiRequest;

export function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  return client.apiUpload<T>(path, options);
}
