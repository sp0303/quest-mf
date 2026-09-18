/**
 * Chart theme tokens mapped directly to DESIGN.md tokens.
 * Adheres to rule §5.9: no raw hex values in components.
 */

export const chartTokens = {
  ink: "var(--color-ink, #0a0a0a)",
  inkSoft: "var(--color-ink-soft, #171717)",
  midGray: "var(--color-mid-gray, #737373)",
  hairline: "var(--color-hairline, #e5e5e5)",
  canvas: "var(--color-canvas, #f5f5f5)",
  paper: "var(--color-paper, #ffffff)",
  ember: "var(--color-ember, #e7000b)",
};

/**
 * Get resolved CSS variable value from document root (needed for canvas stroke/fills)
 */
export function getComputedToken(cssVar: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const val = getComputedStyle(document.documentElement)
    .getPropertyValue(cssVar)
    .trim();
  return val || fallback;
}
