import {
  createApiClient,
  ApiError,
  getApiErrorMessage,
  type UnauthorizedRecovery,
} from "@fantappero/api-client";
import { getWebEnv, resolveApiBaseUrl, WebEnvError } from "../config/env";

export { ApiError, getApiErrorMessage };

let recoverUnauthorized: UnauthorizedRecovery | null = null;

/** Registered by the auth provider so a 401 renews the access token once. */
export function setUnauthorizedRecovery(next: UnauthorizedRecovery | null): void {
  recoverUnauthorized = next;
}

type UploadOptions = {
  accessToken: string;
  file: File;
  fieldName?: string;
};

function resolveBaseUrl(): string {
  try {
    return resolveApiBaseUrl(getWebEnv().viteApiBaseUrl);
  } catch (error) {
    if (error instanceof WebEnvError) {
      throw new ApiError("Servizio non disponibile. Riprova tra poco.", 0, "missing_api_base_url");
    }
    throw error;
  }
}

const client = createApiClient<File>({
  resolveBaseUrl,
  buildUploadValue: (file) => file,
  defaultErrorMessage: () => "Si è verificato un errore.",
  recoverUnauthorized: (input) => {
    if (!recoverUnauthorized) {
      throw input.error;
    }
    return recoverUnauthorized(input);
  },
});

export const apiRequest = client.apiRequest;

export function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  return client.apiUpload<T>(path, options);
}
