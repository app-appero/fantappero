import { Breadcrumb, PageContainer } from "@fantappero/ui";
import { useAuth } from "../auth/AuthContext";
import { ManagerDirectory } from "../components/ManagerDirectory";
import { useLocation } from "../router/simpleRouter";

export function ManagerDirectoryPage() {
  const { activeLeagueId, isDemoMode } = useAuth();
  const { search } = useLocation();

  return (
    <PageContainer
      title="Directory fantallenatori"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Directory" }]} />}
    >
      <ManagerDirectory
        leagueId={activeLeagueId}
        isDemoMode={isDemoMode}
        search={search}
      />
    </PageContainer>
  );
}
