import test from "node:test";
import assert from "node:assert/strict";
import { TOUR_STEPS } from "../tourSteps.ts";

test("Tour steps definition test", () => {
  assert.ok(TOUR_STEPS.length >= 7, "Should have steps for all major features");

  for (const step of TOUR_STEPS) {
    assert.ok(step.id, "Step must have an id");
    assert.ok(step.title, "Step must have a title");
    assert.ok(step.grade5Story.analogy, "Step must have a grade 5 analogy");
    assert.ok(step.grade5Story.description, "Step must have a grade 5 description");
    assert.ok(step.grade5Story.funFact, "Step must have a grade 5 fun fact");
    assert.ok(step.quantExplanation.metric, "Step must have a quant metric");
    assert.ok(step.quantExplanation.details, "Step must have quant details");
  }
});

test("Tour covers all core platform routes", () => {
  const routes = new Set(TOUR_STEPS.map((s) => s.route));
  assert.ok(routes.has("/"), "Screener root route covered");
  assert.ok(routes.has("/calculator"), "Calculator route covered");
  assert.ok(routes.has("/backtest"), "Backtest route covered");
  assert.ok(routes.has("/health"), "Health route covered");
});
