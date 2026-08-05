import type { WireframeUiState } from "@fantappero/contracts";
import type { DirectoryDemoState } from "../screens/directoryDemo";

export type WireframeParams = {
  stato?: WireframeUiState;
};

export type JoinLeagueParams = WireframeParams & {
  code?: string;
};

export type LeagueAdminParams = WireframeParams & {
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

export type RootStackParamList = {
  MainTabs: undefined;
  Auth: WireframeParams | undefined;
  CreateLeague: CreateLeagueParams | undefined;
  LeagueAdmin: LeagueAdminParams | undefined;
  JoinLeague: JoinLeagueParams | undefined;
  ReceivedInvites: ReceivedInvitesParams | undefined;
  AdminPanel: undefined;
  DevSettings: undefined;
};

export type AppTabParamList = {
  Leagues: WireframeParams | undefined;
  Matchday: WireframeParams | undefined;
  Standings: WireframeParams | undefined;
  Roster: WireframeParams | undefined;
  Formation: WireframeParams | undefined;
  Auction: WireframeParams | undefined;
  Market: WireframeParams | undefined;
  Profile: undefined;
};

export type AdminStackParamList = {
  AdminHome: WireframeParams | undefined;
  AdminLeagues: WireframeParams | undefined;
  AdminUsers: WireframeParams | undefined;
};

declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
