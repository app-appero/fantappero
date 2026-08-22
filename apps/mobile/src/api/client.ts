import { createApiClient, ApiError } from "@fantappero/api-client";
import { loadMobileEnv, MobileEnvError } from "../config/env";

export { ApiError };

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
        "URL API non configurato. Imposta EXPO_PUBLIC_API_BASE_URL.",
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
  buildUploadValue: (file) =>
    ({
      uri: file.uri,
      name: file.name,
      type: file.type ?? "text/csv",
    }) as unknown as Blob,
  networkErrorMessage: (baseUrl) =>
    `Connessione non disponibile verso ${baseUrl}. Verifica rete e EXPO_PUBLIC_API_BASE_URL.`,
  invalidResponseMessage: (status) =>
    `Risposta non valida dall'API (HTTP ${status}). Controlla EXPO_PUBLIC_API_BASE_URL.`,
  notFoundMessage: (status) =>
    `Endpoint non trovato (${status}). Controlla EXPO_PUBLIC_API_BASE_URL (API su porta 8001).`,
});

export const apiRequest = client.apiRequest;

export function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  return client.apiUpload<T>(path, options);
}
