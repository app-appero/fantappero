import type { WireframeUiState } from "@fantappero/contracts";
import type { DirectoryDemoState } from "../screens/directoryDemo";

export type WireframeParams = {
  stato?: WireframeUiState;
};

export type JoinLeagueParams = WireframeParams & {
  code?: string;
  token?: string;
};

export type LeagueHomeParams = {
  leagueId?: string;
};

export type LeagueAdminParams = WireframeParams & {
  leagueId?: string;
  stagione?: WireframeUiState;
  calendario?: WireframeUiState;
  directory?: DirectoryDemoState;
};

export type CreateLeagueParams = WireframeParams & {
  directory?: DirectoryDemoState;
};

export type ReceivedInvitesParams = {
  stato?: DirectoryDemoState;
};

export type MatchupDetailParams = {
  slotId: string;
};

/** Dettaglio partita del turno europeo (EP13-P04). */
export type FixtureDetailParams = {
  turnId: string;
  fixtureId: string;
};

export type AppTabParamList = {
  Leagues: WireframeParams | undefined;
  Matchday: WireframeParams | undefined;
  Standings: WireframeParams | undefined;
  Roster: WireframeParams | undefined;
  Formation: WireframeParams | undefined;
  Auction: WireframeParams | undefined;
  Waiver: WireframeParams | undefined;
  Market: WireframeParams | undefined;
  Profile: undefined;
};

export type RootStackParamList = {
  MainTabs: undefined | { screen?: keyof AppTabParamList };
  Auth: WireframeParams | undefined;
  AuthRegister: undefined;
  AuthForgotPassword: undefined;
  AuthResetPassword: { token?: string } | undefined;
  CreateLeague: CreateLeagueParams | undefined;
  LeagueHome: LeagueHomeParams | undefined;
  LeagueAdmin: LeagueAdminParams | undefined;
  JoinLeague: JoinLeagueParams | undefined;
  ReceivedInvites: ReceivedInvitesParams | undefined;
  Notifications: undefined;
  ManagerDirectory: undefined;
  AdminPanel: undefined;
  MatchupDetail: MatchupDetailParams;
  FixtureDetail: FixtureDetailParams;
};

export type AdminStackParamList = {
  AdminHome: WireframeParams | undefined;
  AdminLeagues: WireframeParams | undefined;
  AdminUsers: WireframeParams | undefined;
  AdminListone: WireframeParams | undefined;
  AdminTurni: WireframeParams | undefined;
};

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
