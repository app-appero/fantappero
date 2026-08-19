import { PageContainer } from "@fantappero/ui";
import { DesignSystemShowcase } from "../DesignSystemShowcase";

/** Non-production route preserving EPUI-02 showcase during EPUI-03 layout work. */
export function DevShowcasePage() {
  return (
    <PageContainer title="Design system (dev)">
      <DesignSystemShowcase />
    </PageContainer>
  );
}
