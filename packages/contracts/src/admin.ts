/** Admin panel contracts — platform operator only (EP11-04a). */

export type PlatformRole = "user" | "operator";

export interface AdminOverview {
  operatorId: string;
  operatorDisplayName: string;
  environment: string;
  usersCount: number;
  operatorsCount: number;
  leaguesCount: number;
}

export interface AdminUser {
  id: string;
  email: string;
  displayName: string;
  platformRole: PlatformRole;
  createdAt: string;
}

export interface PaginatedAdminUsers {
  items: AdminUser[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface AdminLeague {
  id: string;
  name: string;
  state: string;
  ownerDisplayName: string | null;
  createdAt: string;
}

export interface PaginatedAdminLeagues {
  items: AdminLeague[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}
