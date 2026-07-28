import { SERVICES, type HealthResponse } from "@fantappero/contracts";
import { colors, spacing, typography } from "@fantappero/ui";

const health: HealthResponse = { status: "ok" };

export function App() {
  return (
    <main
      style={{
        minHeight: "100vh",
        margin: 0,
        padding: spacing.xl,
        background: `radial-gradient(circle at top left, #1c2736, ${colors.background})`,
        color: colors.foreground,
        fontFamily: typography.fontFamily,
      }}
    >
      <p
        style={{
          margin: 0,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: colors.muted,
          fontSize: typography.fontSize.sm,
        }}
      >
        FantApperò
      </p>
      <h1 style={{ margin: `${spacing.md}px 0`, fontSize: typography.fontSize.xl }}>
        Web scaffold
      </h1>
      <p style={{ color: colors.muted, maxWidth: 42 * 16 }}>
        Minimal health page for monorepo bootstrap. No product features yet.
      </p>
      <dl
        style={{
          marginTop: spacing.lg,
          display: "grid",
          gap: spacing.sm,
          fontSize: typography.fontSize.md,
        }}
      >
        <div>
          <dt style={{ color: colors.muted }}>service</dt>
          <dd style={{ margin: 0 }}>{SERVICES.web}</dd>
        </div>
        <div>
          <dt style={{ color: colors.muted }}>health</dt>
          <dd style={{ margin: 0, color: colors.ok }} data-testid="health-status">
            {health.status}
          </dd>
        </div>
      </dl>
    </main>
  );
}
