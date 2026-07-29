import { createLeagueClient } from "../api/leagues";

export { AuthApiError, createAuthClient, type AuthClient } from "../api/auth";
export { createLeagueClient, type LeagueClient } from "../api/leagues";

export function createMobileLeagueClient(baseUrl: string) {
  return createLeagueClient(baseUrl);
}
