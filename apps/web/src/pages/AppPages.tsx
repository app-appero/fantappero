export {
  AuthForgotPasswordPage,
  AuthLoginPage,
  AuthRegisterPage,
  AuthResetPasswordPage,
  AuthVerifyEmailPage,
} from "./auth/AuthPages";
export { AuctionPage } from "./AuctionPage";
export { FormationWireframe as FormationPage } from "../wireframes/screens/formation";
export { CreateLeaguePage } from "./CreateLeaguePage";
export { LeagueAdminPage } from "./LeagueAdminPage";
export { JoinLeaguePage } from "./JoinLeaguePage";
export { LeaguesPage } from "./LeaguesPage";
export { ManagerDirectoryPage } from "./ManagerDirectoryPage";
export { ReceivedInvitesPage } from "./ReceivedInvitesPage";
export { MarketWireframe as MarketPage } from "../wireframes/screens/market";
export { MatchdayWireframe as MatchdayPage } from "../wireframes/screens/matchday";
export {
  OperatorDashboardWireframe as AdminDashboardPage,
  OperatorLeaguesWireframe as AdminLeaguesPage,
  OperatorUsersWireframe as AdminUsersPage,
} from "../wireframes/screens/operatorPanel";
export { RosterWireframe as RosterPage } from "../wireframes/screens/roster";
export { StandingsWireframe as StandingsPage } from "../wireframes/screens/standings";

export { NotFoundPage, ProfilePage } from "./ProfilePage";

/** @deprecated Use AuthLoginPage — kept for wireframe regression tests. */
export { AuthWireframePage as AuthPage } from "../wireframes/screens/auth";
