/** Privacy and account data rights contracts (EP02-04). */

export interface DeleteAccountRequest {
  password: string;
  confirmPhrase: string;
}

export interface PrivacyMessageResponse {
  message: string;
}

/** Confirmation phrase required to delete an account. */
export const DELETE_ACCOUNT_CONFIRMATION_PHRASE = "ELIMINA" as const;

export interface AccountDataExport {
  exportedAt: string;
  formatVersion: string;
  account: {
    id: string;
    email: string;
    emailVerifiedAt: string | null;
    platformRole: string;
    createdAt: string;
    updatedAt: string;
  };
  profile: {
    displayName: string;
    avatarUrl: string | null;
    language: string;
    timezone: string;
    notificationsEmail: boolean;
    notificationsPush: boolean;
    policyConsentAt: string | null;
    policyVersion: string | null;
  };
  leagueMemberships: Array<{
    membershipId: string;
    leagueId: string;
    leagueName: string;
    seasonYear: number;
    leagueState: string;
    role: string;
    historicalDisplayName: string | null;
    joinedAt: string;
  }>;
}
