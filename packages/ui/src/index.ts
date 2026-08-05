/** @fantappero/ui — design tokens and presentational primitives (EPUI-01, EPUI-02). */

export { meetsWcagContrast, contrastRatio, relativeLuminance } from "./accessibility/contrast.js";
export type { ContrastOptions, WcagLevel } from "./accessibility/contrast.js";

export { UiStatePanel } from "./components/UiStatePanel.js";
export type { UiState, UiStatePanelProps } from "./components/UiStatePanel.js";

export { Button } from "./components/Button.js";
export type { ButtonProps, ButtonSize, ButtonVariant } from "./components/Button.js";

export { Input } from "./components/Input.js";
export type { InputProps } from "./components/Input.js";

export { Select } from "./components/Select.js";
export type { SelectOption, SelectProps } from "./components/Select.js";

export { Card, CardBody, CardFooter, CardHeader } from "./components/Card.js";
export type { CardBodyProps, CardFooterProps, CardHeaderProps, CardProps } from "./components/Card.js";

export { Badge } from "./components/Badge.js";
export type { BadgeProps, BadgeVariant } from "./components/Badge.js";

export { Tab, TabList, TabPanel, Tabs } from "./components/Tabs.js";
export type { TabListProps, TabPanelProps, TabProps, TabsProps } from "./components/Tabs.js";

export { Modal } from "./components/Modal.js";
export type { ModalProps } from "./components/Modal.js";

export { ToastProvider, useToast } from "./components/Toast.js";
export type { ToastInput, ToastProviderProps, ToastVariant } from "./components/Toast.js";

export {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "./components/Table.js";
export type {
  TableBodyProps,
  TableCellProps,
  TableHeadProps,
  TableHeaderCellProps,
  TableProps,
  TableRowProps,
} from "./components/Table.js";

export { Skeleton } from "./components/Skeleton.js";
export type { SkeletonProps, SkeletonVariant } from "./components/Skeleton.js";

export { EmptyState } from "./components/EmptyState.js";
export type { EmptyStateProps } from "./components/EmptyState.js";

export { AppShell } from "./components/layout/AppShell.js";
export type { AppShellProps } from "./components/layout/AppShell.js";

export { AppHeader } from "./components/layout/AppHeader.js";
export type { AppHeaderProps } from "./components/layout/AppHeader.js";

export { SidebarNav } from "./components/layout/SidebarNav.js";
export type { NavLinkAnchorProps, NavLinkItem, SidebarNavProps } from "./components/layout/SidebarNav.js";

export { BottomNav } from "./components/layout/BottomNav.js";
export type { BottomNavProps } from "./components/layout/BottomNav.js";

export { PageContainer } from "./components/layout/PageContainer.js";
export type { PageContainerProps } from "./components/layout/PageContainer.js";

export { Breadcrumb } from "./components/layout/Breadcrumb.js";
export type { BreadcrumbItem, BreadcrumbProps } from "./components/layout/Breadcrumb.js";

export { LeagueSelector } from "./components/layout/LeagueSelector.js";
export type { LeagueOption, LeagueSelectorProps } from "./components/layout/LeagueSelector.js";

export { KpiCard } from "./components/domain/KpiCard.js";
export type { KpiCardProps, KpiTrend } from "./components/domain/KpiCard.js";

export { PlayerCard, PlayerRow } from "./components/domain/PlayerCard.js";
export type { PlayerCardProps, PlayerRowProps } from "./components/domain/PlayerCard.js";

export { MatchCard } from "./components/domain/MatchCard.js";
export type { MatchCardProps, MatchStatus } from "./components/domain/MatchCard.js";

export { FormationView } from "./components/domain/FormationView.js";
export type { FormationSlot, FormationViewProps } from "./components/domain/FormationView.js";

export { ResultCard } from "./components/domain/ResultCard.js";
export type { ResultCardProps } from "./components/domain/ResultCard.js";

export { AnomalyIndicator } from "./components/domain/AnomalyIndicator.js";
export type { AnomalyIndicatorProps, AnomalySeverity } from "./components/domain/AnomalyIndicator.js";

export { BrandLogo } from "./components/BrandLogo.js";
export type { BrandLogoProps, BrandLogoSize, BrandLogoVariant } from "./components/BrandLogo.js";

export { AuthFormLayout } from "./components/domain/AuthFormLayout.js";
export type { AuthFormLayoutProps } from "./components/domain/AuthFormLayout.js";

export { AuctionBidPanel } from "./components/domain/AuctionBidPanel.js";
export type { AuctionBidPanelProps } from "./components/domain/AuctionBidPanel.js";

export { StandingsTable } from "./components/domain/StandingsTable.js";
export type { StandingsRow, StandingsTableProps } from "./components/domain/StandingsTable.js";

export { WireframeSection } from "./components/WireframeSection.js";
export type { WireframeSectionProps } from "./components/WireframeSection.js";

export { palette } from "./tokens/palette.js";
export type { PaletteToken } from "./tokens/palette.js";

export { colors, accessibleTextPairs } from "./tokens/colors.js";
export type { ColorToken } from "./tokens/colors.js";

export { spacing, density } from "./tokens/spacing.js";
export type { SpacingToken, DensityToken } from "./tokens/spacing.js";

export {
  typography as typeScale,
  textRoles,
  legacyTypography as typography,
} from "./tokens/typography.js";

export { radius } from "./tokens/radius.js";
export type { RadiusToken } from "./tokens/radius.js";

export { shadows } from "./tokens/shadows.js";
export type { ShadowToken } from "./tokens/shadows.js";

export { motion } from "./tokens/motion.js";
export type { MotionDurationToken } from "./tokens/motion.js";

export { breakpoints, breakpointDown, breakpointUp } from "./tokens/breakpoints.js";
export type { BreakpointToken } from "./tokens/breakpoints.js";

export { zIndex } from "./tokens/zIndex.js";
export type { ZIndexToken } from "./tokens/zIndex.js";

export { iconography } from "./tokens/iconography.js";
export type { IconSizeToken } from "./tokens/iconography.js";

export { illustration } from "./tokens/illustration.js";
export { visualPrinciples } from "./tokens/principles.js";

export { theme } from "./theme.js";
