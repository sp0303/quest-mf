import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Calculator, ArrowRight, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { SEO } from "@/components/common/SEO";

export const CalculatorPage: React.FC = () => {
  const [amount, setAmount] = useState<number>(100000);
  const [buyNav, setBuyNav] = useState<number>(100);
  const [sellNav, setSellNav] = useState<number>(120);
  const [daysHeld, setDaysHeld] = useState<number>(180);
  const [exitLoadRate, setExitLoadRate] = useState<number>(0.01);
  const [exitLoadDays, setExitLoadDays] = useState<number>(365);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/analytics/v1/calculator/net-return", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          initial_amount: amount,
          buy_nav: buyNav,
          sell_nav: sellNav,
          days_held: daysHeld,
          exit_load_rate: exitLoadRate,
          exit_load_days: exitLoadDays,
          stcg_rate: 0.20,
          ltcg_rate: 0.125,
        }),
      });
      return res.json();
    },
  });

  const result = mutation.data;

  // Auto-run once on mount
  React.useEffect(() => {
    mutation.mutate();
  }, []);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <SEO
        title="Mutual Fund Net Return & Capital Gains Tax Calculator (Budget 2024) | quest-mf"
        description="Simulate post-friction mutual fund returns with Stamp Duty (0.005%), Exit Load, STT (0.1%), and post-Budget 2024 LTCG (12.5%) & STCG (20%) tax rates. A Sharat Patnayakuni's product."
        keywords="mutual fund calculator, net return calculator, capital gains tax calculator, mutual fund tax India, LTCG tax mutual funds, STCG tax, exit load, stamp duty, post-tax returns, SIP calculator"
        canonicalPath="/calculator"
      />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink flex items-center gap-2">
          <Calculator className="w-6 h-6 text-ink" aria-hidden="true" />
          Friction & Net-Return Calculator
        </h1>
        <p className="text-sm text-mid-gray mt-1">
          Simulate realistic post-friction net returns including Stamp Duty, Exit Load, STT, and Capital Gains Tax (post-Budget 2024).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Input Parameters Form */}
        <Card className="p-5 space-y-4">
          <h2 className="font-semibold text-sm text-ink uppercase tracking-wider border-b border-hairline pb-2">
            Investment Parameters
          </h2>

          <div>
            <label htmlFor="inv-amount" className="block text-xs font-medium text-mid-gray mb-1">
              Investment Amount (₹)
            </label>
            <input
              id="inv-amount"
              type="number"
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              className="w-full bg-canvas border border-hairline rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ink"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="buy-nav" className="block text-xs font-medium text-mid-gray mb-1">
                Buy NAV (₹)
              </label>
              <input
                id="buy-nav"
                type="number"
                value={buyNav}
                onChange={(e) => setBuyNav(Number(e.target.value))}
                className="w-full bg-canvas border border-hairline rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ink"
              />
            </div>
            <div>
              <label htmlFor="sell-nav" className="block text-xs font-medium text-mid-gray mb-1">
                Sell NAV (₹)
              </label>
              <input
                id="sell-nav"
                type="number"
                value={sellNav}
                onChange={(e) => setSellNav(Number(e.target.value))}
                className="w-full bg-canvas border border-hairline rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ink"
              />
            </div>
          </div>

          <div>
            <label htmlFor="holding-days" className="block text-xs font-medium text-mid-gray mb-1">
              Holding Duration (Days)
            </label>
            <input
              id="holding-days"
              type="number"
              value={daysHeld}
              onChange={(e) => setDaysHeld(Number(e.target.value))}
              className="w-full bg-canvas border border-hairline rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ink"
            />
            <p className="text-[11px] text-mid-gray mt-1">
              {daysHeld <= 365 ? "Short-Term Capital Gains Tax (STCG: 20%)" : "Long-Term Capital Gains Tax (LTCG: 12.5%)"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="exit-load-rate" className="block text-xs font-medium text-mid-gray mb-1">
                Exit Load Rate (%)
              </label>
              <input
                id="exit-load-rate"
                type="number"
                step="0.1"
                value={exitLoadRate * 100}
                onChange={(e) => setExitLoadRate(Number(e.target.value) / 100)}
                className="w-full bg-canvas border border-hairline rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ink"
              />
            </div>
            <div>
              <label htmlFor="exit-load-days" className="block text-xs font-medium text-mid-gray mb-1">
                Exit Load Window (Days)
              </label>
              <input
                id="exit-load-days"
                type="number"
                value={exitLoadDays}
                onChange={(e) => setExitLoadDays(Number(e.target.value))}
                className="w-full bg-canvas border border-hairline rounded-2xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ink"
              />
            </div>
          </div>

          <Button
            className="w-full mt-2"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            aria-label="Calculate Net Return"
          >
            Calculate Net Return
          </Button>
        </Card>

        {/* Results Breakdown */}
        <Card className="p-5 flex flex-col justify-between">
          <div>
            <h2 className="font-semibold text-sm text-ink uppercase tracking-wider border-b border-hairline pb-2 mb-4">
              Return & Friction Breakdown
            </h2>

            {result ? (
              <div className="space-y-2.5 text-sm">
                <div className="flex justify-between py-1 border-b border-hairline">
                  <span className="text-mid-gray">Gross Return</span>
                  <span className="font-semibold tabular-nums">+{result.gross_return_pct}%</span>
                </div>
                <div className="flex justify-between py-1 border-b border-hairline text-ember">
                  <span>Stamp Duty (0.005%)</span>
                  <span className="tabular-nums">-₹{result.stamp_duty}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-hairline text-ember">
                  <span>Exit Load ({daysHeld < exitLoadDays ? `${(exitLoadRate * 100).toFixed(1)}%` : "0%"})</span>
                  <span className="tabular-nums">-₹{result.exit_load}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-hairline text-ember">
                  <span>STT (0.1% on redemption)</span>
                  <span className="tabular-nums">-₹{result.stt}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-hairline text-ember">
                  <span>Capital Gains Tax</span>
                  <span className="tabular-nums">-₹{result.tax}</span>
                </div>
                <div className="flex justify-between py-1 pt-2 font-bold text-base text-ink">
                  <span>Net Proceeds</span>
                  <span className="tabular-nums">₹{result.net_proceeds.toLocaleString()}</span>
                </div>
              </div>
            ) : (
              <div className="py-16 text-center text-mid-gray text-sm">
                Click calculate to inspect net return breakdown.
              </div>
            )}
          </div>

          {result && (
            <div className="mt-6 p-4 rounded-2xl bg-canvas border border-hairline">
              <div className="text-xs text-mid-gray uppercase font-semibold">Net Annualized Return</div>
              <div className="text-3xl font-bold text-ink tabular-nums mt-1">
                +{result.net_return_pct}%
              </div>
              <p className="text-xs text-mid-gray mt-1">
                Net profit of ₹{result.net_profit.toLocaleString()} on ₹{amount.toLocaleString()} capital.
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
