import { Breadcrumb, PageContainer } from "@fantappero/ui";
import { useState } from "react";
import { AdminAppUsagePanel } from "./AdminAppUsagePanel";
import { AdminAppVersionPanel } from "./AdminAppVersionPanel";

/**
 * «Versione app» (release 1.4, canvas «Pannello operatore»): voce di menù a sé, dopo
 * «Segnalazioni». Dentro lo stesso modulo che prima stava in fondo alla prima pagina del
 * pannello: versione, versionCode, link e messaggio, con lo stesso comportamento.
 *
 * Decisione di Rosario del 23/11: sotto il modulo «Chi ha quale versione», versione per
 * versione; si rilegge dopo ogni salvataggio.
 */
export function AdminAppVersionPage() {
  const [reloadKey, setReloadKey] = useState(0);
  return (
    <PageContainer
      title="Versione app"
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Versione app" }]} />
      }
    >
      <div className="fa-admin-appversion-page" data-testid="admin-appversion-page">
        <AdminAppVersionPanel hideTitle onSaved={() => setReloadKey((key) => key + 1)} />
        <AdminAppUsagePanel reloadKey={reloadKey} />
      </div>
    </PageContainer>
  );
}
