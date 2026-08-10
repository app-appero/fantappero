import type {
  PolicyConsentRequest,
  UpdateProfileRequest,
  UserProfile,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export function fetchProfile(accessToken: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me", { accessToken });
}

export function updateProfile(
  accessToken: string,
  body: UpdateProfileRequest,
): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me", {
    method: "PATCH",
    body,
    accessToken,
  });
}

export function updateInviteAvailability(
  accessToken: string,
  availableForInvites: boolean,
): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/disponibilita-inviti", {
    method: "PATCH",
    body: { availableForInvites },
    accessToken,
  });
}

export function recordPolicyConsent(
  accessToken: string,
  body: PolicyConsentRequest,
): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me/policy-consent", {
    body,
    accessToken,
  });
}
