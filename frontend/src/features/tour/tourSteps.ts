import type { TourStep } from "./types";

export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    route: "/",
    targetSelector: '[data-tour="brand-logo"]',
    placement: "bottom",
    badge: "🎒 5th Grade Concept 1",
    title: "What is a Mutual Fund?",
    grade5Story: {
      analogy: "The Giant School Picnic Basket",
      description:
        "Imagine 100 students pooling ₹50 each to buy 40 different fruits and snacks. If one fruit gets squished, everyone still enjoys a great picnic! That is diversification.",
      funFact: "NAV (Net Asset Value) is simply the price of 1 slice of that picnic pizza!",
    },
    quantExplanation: {
      metric: "Canonical Direct-Growth Series",
      details:
        "quest-mf screens canonical direct-growth mutual funds where TER is already factored into NAV with zero lookahead bias.",
    },
  },
  {
    id: "category-filter",
    route: "/",
    targetSelector: '[data-tour="screener-filters"]',
    placement: "bottom",
    badge: "🏃 5th Grade Concept 2",
    title: "Fair Playground (Categories)",
    grade5Story: {
      analogy: "Racing in Your Own Grade",
      description:
        "You would never race a 5th grader against a 12th grader! This filter ensures Large-Cap sprinters only race against other Large-Cap sprinters.",
      funFact: "A fair race needs at least 8 competitors in the same class.",
    },
    quantExplanation: {
      metric: "Point-in-Time Peer Grouping",
      details:
        "Categories and benchmark TRI assignments are looked up point-in-time (valid @> as_of_date). Minimum 8 peers required for percentiles.",
    },
  },
  {
    id: "quadrant-matrix",
    route: "/",
    targetSelector: '[data-tour="quadrant-matrix"]',
    placement: "bottom",
    badge: "🦸 5th Grade Concept 3",
    title: "The Superhero Matrix (2×2)",
    grade5Story: {
      analogy: "Speed vs. Personal Best Form",
      description:
        "X-axis is how fast you ran compared to friends. Y-axis is how close you are to your personal best! The top-right box (Q1) holds champions beating friends AND in peak form.",
      funFact: "Q1 = Fast today AND running better than their own usual self!",
    },
    quantExplanation: {
      metric: "Peer Percentile vs. SHP (3M)",
      formula: "Quadrant = (Peer % ≥ 50, SHP % ≥ 50)",
      details:
        "Combines cross-sectional peer percentile rank with own-history Sharpe percentile (SHP) excluding t itself.",
    },
  },
  {
    id: "screener-table",
    route: "/",
    targetSelector: '[data-tour="screener-table"]',
    placement: "top",
    badge: "📊 5th Grade Concept 4",
    title: "The Fair Talent Scorecard",
    grade5Story: {
      analogy: "Looking Beyond Just Yesterday",
      description:
        "A student who got an A+ on one quiz might just be lucky. The scorecard looks at consistency across 3 months, 1 year, and 3 years to find steady performers.",
      funFact: "A smooth, steady bicycle ride is safer than a wild roller coaster!",
    },
    quantExplanation: {
      metric: "Composite Quant Rank & Rolling Windows",
      details:
        "Multi-factor model evaluating rolling returns, benchmark TRI alpha, and Sharpe ratios across CAL_3M, CAL_1Y, and CAL_3Y.",
    },
  },
  {
    id: "calculator",
    route: "/calculator",
    targetSelector: '[data-tour="calculator-card"]',
    placement: "right",
    badge: "🍬 5th Grade Concept 5",
    title: "The Candy Tollbooth (Net Returns)",
    grade5Story: {
      analogy: "What Actually Reaches Your Pocket",
      description:
        "If you win 10 candies in a fair game, you might pay 1 candy for ticket fees and 1 candy in taxes. This calculator shows your true pocket money after all tollbooths.",
      funFact: "Holding longer than 1 year often cuts your tax toll in half!",
    },
    quantExplanation: {
      metric: "Post-Friction Realized Yield",
      details:
        "Simulates Stamp Duty (0.005%), Exit Loads, STT (0.1%), and post-Budget 2024 LTCG (12.5%) & STCG (20%) tax schedules.",
    },
  },
  {
    id: "backtest",
    route: "/backtest",
    targetSelector: '[data-tour="backtest-form"]',
    placement: "bottom",
    badge: "⏳ 5th Grade Concept 6",
    title: "The Time Machine (Backtester)",
    grade5Story: {
      analogy: "No Cheating With Tomorrow's Answers",
      description:
        "Jump into a time machine to 2019! Test your investing rules month-by-month as if tomorrow is still a mystery. Did your strategy survive the bumpy years?",
      funFact: "Real games have small delays before your moves take effect.",
    },
    quantExplanation: {
      metric: "Walk-Forward Execution Simulation",
      details:
        "Periodic rebalancing with execution lag (EXEC_LAG), switch bounds, and minimum holding rules with zero lookahead bias.",
    },
  },
  {
    id: "data-health",
    route: "/health",
    targetSelector: '[data-tour="data-health-grid"]',
    placement: "bottom",
    badge: "🥛 5th Grade Concept 7",
    title: "The Fresh Milk Quality Stamp",
    grade5Story: {
      analogy: "Checking the Expiry & Ingredients",
      description:
        "Just like checking the date stamped on a bottle of milk, this dashboard proves our prices were freshly delivered from AMFI with zero missing days.",
      funFact: "Healthy data means no bad surprises in your charts!",
    },
    quantExplanation: {
      metric: "Database Ingestion & Cache Telemetry",
      details:
        "Monitors raw AMFI daily NAV ingestion, Timescale hypertables, and Redis cache liveness.",
    },
  },
];
