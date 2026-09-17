# quest-mf — Low-Level Design: Frontend (React)

**Stack:** React 19 · TypeScript 5 (strict) · Vite 6 · React Router 7 (data router, lazy routes) · TanStack Query v5 · Zustand · TanStack Table + TanStack Virtual · Apache ECharts 5 (modular) · Tailwind CSS v4 · shadcn/ui (Radix primitives) · lucide-react · openapi-typescript + openapi-fetch · react-hook-form + zod (forms only) · Comlink (web workers) · Vitest · Testing Library · Playwright · MSW
**Visual system:** [`docs/DESIGN.md`](../DESIGN.md) — shadcn-style monochrome, Geist, 18 px / 24 px radii
**Parent:** [HLD](HLD.md)

---

## 1. Principles

1. **Component-based, no god files.** One component per file. ≤ 150 lines per component file and ≤ 40 lines of JSX per component; if it grows, split it.
2. **Feature-sliced structure.** Code is grouped by feature. Shared UI lives in `components/ui`. Features never import from other features' internals.
3. **Server state ≠ client state.** TanStack Query owns server data. Zustand owns UI/session state. The URL owns filter state. Nothing is duplicated between them.
4. **Everything heavy is lazy.** Routes, charts, the table engine and workers are all in separate chunks.
5. **Render less.** Use virtualisation, memoised rows, stable selectors and deferred values.
6. **Design tokens only.** No hex values in components; use Tailwind theme tokens from DESIGN.md.

## 2. Folder structure

```text
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── eslint.config.js
├── .size-limit.json
├── public/fonts/geist-*.woff2
└── src/
    ├── main.tsx                     # createRoot, providers
    ├── app/
    │   ├── providers/
    │   │   ├── QueryProvider.tsx
    │   │   ├── ThemeProvider.tsx
    │   │   └── AuthGate.tsx
    │   ├── router/
    │   │   ├── routes.tsx           # route objects with lazy()
    │   │   ├── RouteError.tsx
    │   │   └── prefetch.ts          # route chunk + data prefetch on hover
    │   └── layout/
    │       ├── AppShell.tsx
    │       ├── Sidebar.tsx
    │       ├── SidebarNavItem.tsx
    │       ├── Topbar.tsx
    │       ├── CommandSearch.tsx     # ⌘K
    │       └── DisclaimerFooter.tsx
    ├── pages/                        # thin: compose features, no logic
    │   ├── ScreenerPage.tsx
    │   ├── FundDetailPage.tsx
    │   ├── ComparePage.tsx
    │   ├── BacktestListPage.tsx
    │   ├── BacktestDetailPage.tsx
    │   ├── CalculatorPage.tsx
    │   ├── DataHealthPage.tsx
    │   ├── LoginPage.tsx
    │   └── NotFoundPage.tsx
    ├── features/
    │   ├── screener/
    │   │   ├── api/                  # query keys + hooks
    │   │   │   ├── keys.ts
    │   │   │   ├── useScreener.ts
    │   │   │   └── useMatrix.ts
    │   │   ├── components/
    │   │   │   ├── ScreenerFilters.tsx
    │   │   │   ├── CategorySelect.tsx
    │   │   │   ├── WindowSelect.tsx
    │   │   │   ├── ScreenerTable.tsx
    │   │   │   ├── ScreenerRow.tsx
    │   │   │   ├── ScoreCell.tsx
    │   │   │   ├── PercentCell.tsx
    │   │   │   ├── FlagBadges.tsx
    │   │   │   ├── ConfidenceBadge.tsx
    │   │   │   └── QuadrantChart.tsx       # lazy (ECharts)
    │   │   ├── hooks/
    │   │   │   └── useScreenerParams.ts    # URL ⇄ typed filters
    │   │   ├── model/
    │   │   │   ├── columns.ts
    │   │   │   └── types.ts
    │   │   └── index.ts                    # public API of the feature
    │   ├── fund-detail/
    │   │   ├── api/ (useFundSummary, useNavSeries, useRolling, useDistribution, useRisk, useEvents, useCosts)
    │   │   ├── components/
    │   │   │   ├── FundHeader.tsx
    │   │   │   ├── StatGrid.tsx
    │   │   │   ├── StatBlock.tsx
    │   │   │   ├── EvidenceStrip.tsx
    │   │   │   ├── NavChartCard.tsx         # lazy chart inside
    │   │   │   ├── RollingReturnCard.tsx
    │   │   │   ├── ActiveReturnCard.tsx
    │   │   │   ├── DrawdownCard.tsx
    │   │   │   ├── DistributionCard.tsx
    │   │   │   ├── RiskTable.tsx
    │   │   │   ├── CostPanel.tsx
    │   │   │   ├── EventTimeline.tsx
    │   │   │   └── WindowTabs.tsx
    │   │   └── index.ts
    │   ├── compare/
    │   ├── backtest/
    │   │   ├── api/ (useRuns, useRun, useRunSeries, useCreateRun, useRunEvents ← SSE)
    │   │   └── components/ (RunForm, RunList, RunStatus, EquityCurveCard, IcSeriesCard, QuintileBars, RegimeTable)
    │   ├── calculator/
    │   ├── data-health/
    │   ├── search/
    │   └── auth/
    ├── components/
    │   ├── ui/                       # shadcn/ui generated + token-styled (Button, Card, Badge, Input, Select, Tabs, Tooltip, Dialog, Skeleton, Table, Breadcrumb, Command)
    │   ├── charts/
    │   │   ├── EChart.tsx            # the only ECharts wrapper (lazy-registered modules)
    │   │   ├── echarts.ts            # echarts/core + selected charts/components
    │   │   ├── theme.ts              # monochrome theme from tokens
    │   │   └── options/              # pure option builders (lineOption.ts, histogramOption.ts, scatterOption.ts)
    │   ├── data/
    │   │   ├── VirtualTable.tsx
    │   │   ├── NumberCell.tsx
    │   │   └── EmptyState.tsx
    │   └── feedback/
    │       ├── PageSkeleton.tsx
    │       ├── CardSkeleton.tsx
    │       └── ErrorCard.tsx
    ├── lib/
    │   ├── api/
    │   │   ├── client.ts             # openapi-fetch instance, auth header, refresh on 401
    │   │   ├── schema.d.ts           # generated — DO NOT EDIT
    │   │   └── columnar.ts           # columns/rows → typed objects (lazy)
    │   ├── format/ (percent.ts, currency.ts, date.ts)   # Intl formatters, memoised
    │   ├── sse.ts
    │   └── env.ts
    ├── stores/
    │   ├── authStore.ts             # access token (memory only), user
    │   ├── uiStore.ts               # sidebar, density, theme, command palette
    │   └── compareStore.ts          # selected funds for compare (persisted)
    ├── workers/
    │   └── table.worker.ts          # sort/filter large arrays (Comlink)
    ├── styles/
    │   ├── globals.css              # @import "tailwindcss"; @theme tokens
    │   └── fonts.css
    └── test/ (setup.ts, msw handlers)
```

**Import rules** (enforced by `eslint-plugin-boundaries`):

| From ↓ may import → | app | pages | features | components | lib | stores |
|---|---|---|---|---|---|---|
| app | ✓ | ✓ | ✓ (index only) | ✓ | ✓ | ✓ |
| pages | — | — | ✓ (index only) | ✓ | ✓ | ✓ |
| features | — | — | own folder only | ✓ | ✓ | ✓ |
| components | — | — | — | ✓ | ✓ | — |
| lib | — | — | — | — | ✓ | — |

## 3. Routing and lazy loading

```tsx
// app/router/routes.tsx
const ScreenerPage = lazy(() => import("@/pages/ScreenerPage"));
const FundDetailPage = lazy(() => import("@/pages/FundDetailPage"));
// …

export const router = createBrowserRouter([
  { path: "/login", lazy: () => import("@/pages/LoginPage").then(m => ({ Component: m.default })) },
  {
    element: <AuthGate><AppShell /></AuthGate>,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Navigate to="/screener" replace /> },
      { path: "screener", element: <S><ScreenerPage /></S> },
      { path: "funds/:portfolioId", element: <S><FundDetailPage /></S>,
        loader: fundLoader(queryClient) },           // ensureQueryData → no waterfall
      { path: "compare", element: <S><ComparePage /></S> },
      { path: "backtests", element: <S><BacktestListPage /></S> },
      { path: "backtests/:runId", element: <S><BacktestDetailPage /></S> },
      { path: "calculator", element: <S><CalculatorPage /></S> },
      { path: "data-health", element: <S><DataHealthPage /></S> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
// S = <Suspense fallback={<PageSkeleton/>}>
```

**Prefetch:** `SidebarNavItem` and `ScreenerRow` call `prefetchRoute(path)` on `pointerenter`/`focus`. This imports the chunk and runs `queryClient.prefetchQuery` for the fund summary, so a click renders instantly.

**Chunking** (`vite.config.ts` → `build.rollupOptions.output.manualChunks`):

| Chunk | Contents | Loaded when |
|---|---|---|
| `index` | React, router, query, zustand, shell, ui primitives | always (≤ 150 KB gz budget) |
| `echarts` | echarts/core + line/bar/scatter/candlestick + grid/tooltip/dataZoom/markLine | first chart card is visible (IntersectionObserver) |
| `table` | @tanstack/react-table + virtual | screener / backtest holdings |
| `forms` | react-hook-form + zod | calculator / run form |
| route chunks | one per page | navigation / hover |

## 4. State management

| State | Owner | Examples |
|---|---|---|
| Server data | **TanStack Query** | screener rows, fund summary, series, runs |
| Filters / selection that should be shareable | **URL search params** (`useScreenerParams`) | category, window, sort, min confidence |
| UI state | **Zustand** (`uiStore`) | sidebar collapsed, density, command-palette open |
| Session | **Zustand** (`authStore`, in memory; no localStorage for tokens) | access token, user |
| Cross-page selection | **Zustand + persist** (`compareStore`, localStorage in try/catch) | funds to compare (≤ 4) |
| Form state | react-hook-form | calculator, run config |

### 4.1 Query conventions

```ts
// features/screener/api/keys.ts
export const screenerKeys = {
  all: ["screener"] as const,
  list: (p: ScreenerParams, asOf: string) => [...screenerKeys.all, "list", asOf, p] as const,
  matrix: (c: string, m: string, asOf: string) => [...screenerKeys.all, "matrix", asOf, c, m] as const,
};

// features/screener/api/useScreener.ts
export function useScreener(p: ScreenerParams) {
  const asOf = useLatestAsOf();                      // /screener/latest, staleTime 5 min
  return useQuery({
    queryKey: screenerKeys.list(p, asOf),
    queryFn: ({ signal }) => fetchScreener(p, signal),
    enabled: !!asOf,
    placeholderData: keepPreviousData,               // no flicker when filters change
    staleTime: 10 * 60_000,                          // data changes nightly
    gcTime: 60 * 60_000,
    select: toRows,                                  // columnar → objects, memoised
  });
}
```

Global defaults: `refetchOnWindowFocus: false`, `retry: 1` (0 for 4xx), `networkMode: "online"`. Including `as_of` in the key means a new nightly publish naturally creates fresh cache entries.

### 4.2 Zustand conventions

```ts
export const useUiStore = create<UiState>()((set) => ({
  sidebarCollapsed: false,
  density: "compact",
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
// Always select narrowly — never destructure the whole store:
const collapsed = useUiStore((s) => s.sidebarCollapsed);
```

## 5. Performance playbook

| Technique | Where |
|---|---|
| `React.lazy` + `Suspense` per route and per chart card | router, `*ChartCard` |
| Visibility-gated chart mount (`useInView`) | all chart cards |
| `React.memo` on `ScreenerRow`, `NumberCell`, and stable `columns` (module-level) | table |
| TanStack Virtual (row height 40 px, overscan 8) | `VirtualTable` |
| `useDeferredValue` for search text and filter changes; `startTransition` for sort | screener, search |
| Web Worker (Comlink) for sort/filter when rows > 5,000 | `table.worker.ts` |
| Columnar payload → typed arrays for charts (no object mapping) | `EChart` + option builders |
| ECharts `sampling: 'lttb'`, `progressive` rendering, `animation: false` for > 2k points | `lineOption.ts` |
| Intl formatters created once (module scope) | `lib/format` |
| `fetch` with `AbortSignal` (from Query) | all queries |
| Font preload + `font-display: swap`; system fallback | `index.html` |
| Hashed immutable assets + precompressed `.br` / `.gz` (vite-plugin-compression) | build |
| `<link rel="preconnect">` to the API origin (same origin in prod) | `index.html` |
| No CSS-in-JS runtime; Tailwind only | global |
| React Compiler (babel plugin) enabled when stable for the codebase | build |

**Budgets (CI-enforced):** initial JS ≤ 150 KB gz; any route chunk ≤ 80 KB gz; `echarts` ≤ 250 KB gz; LCP ≤ 1.5 s, INP ≤ 200 ms, CLS ≤ 0.05 (Lighthouse CI, mobile profile).

## 6. Design-system implementation

### 6.1 Tokens → Tailwind v4

`styles/globals.css` copies the `@theme` block from DESIGN.md verbatim (colors, type scale, spacing, radii, shadows). Components use only token classes: `bg-paper`, `bg-canvas`, `text-ink`, `text-mid-gray`, `border-hairline`, `rounded-3xl` (cards, 24 px), `rounded-2xl` (buttons/inputs/badges, 18 px), `shadow-subtle`.

### 6.2 Component mapping

| DESIGN.md component | Implementation |
|---|---|
| Primary Filled Button | `<Button variant="default">` → `bg-ink text-[#fafafa] rounded-2xl h-9 px-3 text-sm font-medium` |
| Secondary Ghost Button | `variant="secondary"` → `bg-canvas text-ink` |
| Outline Button | `variant="outline"` → `border border-hairline bg-transparent` |
| Card | `<Card>` → `bg-paper rounded-3xl border border-hairline shadow-subtle p-5` |
| Nested Card Header/Footer | `<CardHeader>` / `<CardFooter>` with asymmetric radius |
| Input / Search Trigger | `<Input>` → `bg-canvas rounded-2xl px-2.5 py-2 focus:ring-1 ring-hairline`; ⌘K hint on `CommandSearch` |
| Badge solid / soft / outline | `<Badge variant="solid|soft|outline">` → `rounded-2xl px-2 py-0.5 text-xs font-medium` |
| Sidebar Surface | `Sidebar` → `bg-surface-alt` full height |
| Breadcrumb | `components/ui/breadcrumb` |
| Stat Block | `StatBlock` → caption label uppercase `text-mid-gray tracking-[0.05em]`; value `text-3xl/4xl font-semibold tracking-tight` |
| Destructive | `variant="destructive"` → `text-ember` |

### 6.3 Domain-specific decisions (deviations are documented)

DESIGN.md is achromatic, and a finance UI must still show gains and losses. The rules are:

- **Positive values:** `text-ink` with an explicit `+` sign and a thin ▲ glyph.
- **Negative values:** `text-ember` with `−` and ▼. This is the **only** non-destructive use of Ember.
  - DESIGN.md itself is ambiguous here. Its token table calls Ember a "supporting accent", while its Do's list reserves it for destructive use. We choose "negative numbers + destructive" and nothing else.
- **Charts:** a monochrome series palette (`#0a0a0a`, `#737373`, `#a3a3a3`, `#d4d4d4`), differentiated by dash pattern and marker, not hue. The benchmark is always dashed `#737373`. Drawdown areas use an Ember fill at 12 % opacity. Percentile bands are grey fills at stepped opacity.
- **Tables:** they sit inside cards (the card keeps the 24 px radius; the inner table is square-edged, which is an accepted exception for data grids). Numbers use `font-variant-numeric: tabular-nums`, right-aligned.
- **Dark mode:** tokens are redefined under `[data-theme="dark"]` (ink ↔ paper inversion). Every component must render correctly in both themes.
- **Accessibility:** colour is never the only signal (signs and glyphs); visible focus ring; WCAG AA contrast; `aria-sort` on table headers; charts have a tabular "View data" fallback.

## 7. Page compositions

### 7.1 Screener (`/screener`)

```text
AppShell
└─ ScreenerPage
   ├─ Breadcrumb
   ├─ ScreenerFilters (Card)         ← URL params
   │   ├─ CategorySelect · WindowSelect · ModelSelect
   │   └─ ConfidenceToggle · InvestableToggle · MaxTerInput
   ├─ Grid (lg: 2/3 + 1/3)
   │   ├─ ScreenerTable (Card, VirtualTable)
   │   │   └─ ScreenerRow × n → ScoreCell · PercentCell · FlagBadges · ConfidenceBadge
   │   └─ QuadrantChart (Card, lazy)  ← x = peer pct, y = SHP
   └─ DataAsOfNote
```

### 7.2 Fund detail (`/funds/:id`)

```text
FundDetailPage
├─ FundHeader (name, AMC, category badge, benchmark, flags, compare toggle)
├─ StatGrid → StatBlock × 8 (1M/3M/6M/1Y, peer pct, SHP, alpha 3M, IR 3Y)
├─ EvidenceStrip (component bars: momentum / persistence / LT quality / risk / cost)
├─ WindowTabs [1M | 3M | 6M | 1Y]
├─ NavChartCard (NAV + SMA20/50/200 + benchmark rebased)       lazy
├─ RollingReturnCard  · ActiveReturnCard                        lazy
├─ DrawdownCard · DistributionCard (today marker + P10–P90)     lazy
├─ RiskTable · CostPanel
└─ EventTimeline
```

Data loading: the route `loader` ensures `summary` (a single small call). Each card owns its own query and skeleton, so there is no request waterfall and the cards stream in independently.

### 7.3 Backtest detail

Uses `useRunEvents(runId)` (an EventSource via `lib/sse.ts`) → updates the query cache with `setQueryData` → `RunStatus` progress bar. On `done`, it invalidates `run` and `series`.

## 8. API client

- Types are generated from each service's OpenAPI: `npm run gen:api` → `src/lib/api/schema.d.ts`. CI fails if it is stale.
- `openapi-fetch` client with middleware:
  - adds `Authorization: Bearer <token>` from `authStore`;
  - on 401, performs a single-flight `POST /api/auth/v1/refresh` and replays the request once;
  - adds `X-Request-ID`.
- Dev: Vite proxy `/api/<svc>` → `http://localhost:80xx` (the port table in [DEPLOYMENT-OCI.md](DEPLOYMENT-OCI.md)).

## 9. Testing

| Level | Tool | Target |
|---|---|---|
| Unit | Vitest | formatters, option builders, columnar mapper, stores |
| Component | Testing Library + MSW | each feature component (loading / empty / error / data states) |
| E2E | Playwright | login → screener filter → fund page → run backtest |
| Visual | Playwright screenshots (light + dark) | ui primitives, key pages |
| Perf | Lighthouse CI + size-limit | budgets in §5 |
| A11y | axe (Playwright) | no serious violations |

## 10. Scripts

```json
{
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview --port 3000",
  "lint": "eslint . && prettier --check .",
  "typecheck": "tsc -b --noEmit",
  "test": "vitest run",
  "e2e": "playwright test",
  "gen:api": "node scripts/gen-api.mjs",
  "size": "size-limit"
}
```
