import type {
  PolicyConsentRequest,
  UpdateProfileRequest,
  UserProfile,
} from "@fantappero/contracts";
import { apiRequest, apiUpload } from "./client";

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

export function uploadAvatar(
  accessToken: string,
  file: { uri: string; name: string; type?: string },
): Promise<UserProfile> {
  return apiUpload<UserProfile>("/profile/me/avatar", { accessToken, file });
}

export function removeAvatar(accessToken: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me/avatar", {
    method: "DELETE",
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
