import type {
  AdminOverview,
  AdminUser,
  PaginatedAdminLeagues,
  PaginatedAdminUsers,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export function fetchAdminOverview(accessToken: string): Promise<AdminOverview> {
  return apiRequest<AdminOverview>("/admin/overview", { accessToken });
}

export function fetchAdminUsers(
  accessToken: string,
  options: { query?: string; page?: number } = {},
): Promise<PaginatedAdminUsers> {
  const params = new URLSearchParams();
  if (options.query) {
    params.set("query", options.query);
  }
  if (options.page) {
    params.set("page", String(options.page));
  }
  const qs = params.toString();
  return apiRequest<PaginatedAdminUsers>(`/admin/users${qs ? `?${qs}` : ""}`, { accessToken });
}

export function promoteOperator(accessToken: string, userId: string): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}/promote`, {
    accessToken,
    method: "POST",
  });
}

export function revokeOperator(accessToken: string, userId: string): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}/revoke`, {
    accessToken,
    method: "POST",
  });
}

export function fetchAdminLeagues(
  accessToken: string,
  options: { query?: string; page?: number } = {},
): Promise<PaginatedAdminLeagues> {
  const params = new URLSearchParams();
  if (options.query) {
    params.set("query", options.query);
  }
  if (options.page) {
    params.set("page", String(options.page));
  }
  const qs = params.toString();
  return apiRequest<PaginatedAdminLeagues>(`/admin/leagues${qs ? `?${qs}` : ""}`, { accessToken });
}
