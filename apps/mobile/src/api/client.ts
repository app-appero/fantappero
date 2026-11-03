import {
  createApiClient,
  ApiError,
  getApiErrorMessage,
  type UnauthorizedRecovery,
} from "@fantappero/api-client";
import { File } from "expo-file-system";
import { loadMobileEnv, MobileEnvError } from "../config/env";
import { buildUploadFormValue } from "./uploadValue";

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
  // Con Expo 58 `{ uri, name, type }` da solo non basta: vedi `uploadValue.ts`.
  buildUploadValue: (file) =>
    buildUploadFormValue(file, (uri) => new File(uri).bytes()) as unknown as Blob,
  networkErrorMessage: () => "Connessione non disponibile. Riprova tra poco.",
  invalidResponseMessage: () => "Risposta non valida. Riprova tra poco.",
  notFoundMessage: () => "Risorsa non trovata. Riprova tra poco.",
});

export const apiRequest = client.apiRequest;

export const apiUploadForm = client.apiUploadForm;

/** URL assoluto di un path relativo dell'API (es. il link firmato di un allegato). */
export function buildApiUrl(path: string): string {
  return `${resolveApiBaseUrl()}${path}`;
}

export function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  return client.apiUpload<T>(path, options);
}
