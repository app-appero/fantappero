export {
  AuthForgotPasswordPage,
  AuthLoginPage,
  AuthRegisterPage,
  AuthResetPasswordPage,
  AuthVerifyEmailPage,
} from "./auth/AuthPages";
export { AuctionPage } from "./AuctionPage";
export { FormationPage } from "./FormationPage";
export { CreateLeaguePage } from "./CreateLeaguePage";
export { LeagueAdminPage } from "./LeagueAdminPage";
export { LeagueHomePage } from "./LeagueHomePage";
export { JoinLeaguePage } from "./JoinLeaguePage";
export { LeaguesPage } from "./LeaguesPage";
export { ManagerDirectoryPage } from "./ManagerDirectoryPage";
export { ReceivedInvitesPage } from "./ReceivedInvitesPage";
export { MarketWireframe as MarketPage } from "../wireframes/screens/market";
export { MatchdayPage } from "./MatchdayPage";
export {
  OperatorDashboardWireframe as AdminDashboardPage,
  OperatorLeaguesWireframe as AdminLeaguesPage,
  OperatorUsersWireframe as AdminUsersPage,
} from "../wireframes/screens/operatorPanel";
export { RosterPage } from "./RosterPage";
export { StandingsWireframe as StandingsPage } from "../wireframes/screens/standings";

export { NotFoundPage, ProfilePage } from "./ProfilePage";

/** @deprecated Use AuthLoginPage — kept for wireframe regression tests. */
export { AuthWireframePage as AuthPage } from "../wireframes/screens/auth";
