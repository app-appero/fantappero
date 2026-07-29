import {
  type ApiErrorResponse,
  type CompetitionResponse,
  type CreateLeagueRequest,
  type LeagueResponse,
} from "@fantappero/contracts";

import { AuthApiError } from "./auth";

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
  headers.set("Content-Type", "application/json");
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

export function createLeagueClient(baseUrl: string) {
  return {
    listCompetitions(token: string) {
      return request<CompetitionResponse[]>(baseUrl, "/leagues/competitions", {}, token);
    },
    createLeague(token: string, body: CreateLeagueRequest) {
      return request<LeagueResponse>(
        baseUrl,
        "/leagues",
        { method: "POST", body: JSON.stringify(body) },
        token,
      );
    },
    getLeague(token: string, leagueId: string) {
      return request<LeagueResponse>(baseUrl, `/leagues/${leagueId}`, {}, token);
    },
  };
}

export type LeagueClient = ReturnType<typeof createLeagueClient>;
