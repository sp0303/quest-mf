import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle, Database, Server } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SEO } from "@/components/common/SEO";

export const DataHealthPage: React.FC = () => {
  const { data: freshness, isLoading } = useQuery({
    queryKey: ["freshness"],
    queryFn: async () => {
      const res = await fetch("/api/market/v1/freshness");
      return res.json();
    },
  });

  const { data: latestPublish } = useQuery({
    queryKey: ["latestPublish"],
    queryFn: async () => {
      const res = await fetch("/api/screener/v1/latest");
      return res.json();
    },
  });

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <SEO
        title="Platform & Data Health Diagnostics | quest-mf"
        description="Monitor AMFI NAV database records, ingestion pipeline freshness, and cloud PostgreSQL and Redis service health."
        keywords="mutual fund data health, AMFI NAV database, data freshness, cloud postgres, redis cache health"
        canonicalPath="/health"
      />
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink flex items-center gap-2">
          <Activity className="w-6 h-6 text-ink" aria-hidden="true" />
          Platform & Data Health
        </h1>
        <p className="text-sm text-mid-gray mt-1">
          Monitor database records, cache freshness, and pipeline execution logs.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-mid-gray uppercase font-semibold">PostgreSQL</span>
            <Badge variant="solid" className="bg-ink text-paper">Connected</Badge>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tabular-nums">
              {freshness?.total_nav_rows?.toLocaleString() || "0"}
            </div>
            <div className="text-xs text-mid-gray mt-1">Total NAV Price Records</div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-mid-gray uppercase font-semibold">Tracked Schemes</span>
            <Badge variant="soft">Active</Badge>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tabular-nums">
              {freshness?.total_schemes || "0"}
            </div>
            <div className="text-xs text-mid-gray mt-1">Portfolios Seeded</div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-mid-gray uppercase font-semibold">Latest Snapshot</span>
            <Badge variant="soft">Up to date</Badge>
          </div>
          <div className="mt-4">
            <div className="text-2xl font-bold tabular-nums">
              {freshness?.last_nav_date || latestPublish?.as_of_date || "Live"}
            </div>
            <div className="text-xs text-mid-gray mt-1">Latest NAV Business Date</div>
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
          <Server className="w-4 h-4 text-mid-gray" />
          Environment & Architecture Status
        </h2>
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between py-2 border-b border-hairline">
            <span className="text-mid-gray">Topology</span>
            <span className="font-semibold text-ink">Modular Monolith (Port 8000)</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-hairline">
            <span className="text-mid-gray">Cloud Database Tier</span>
            <span className="font-semibold text-ink">PostgreSQL 16 @ 140.245.194.172:5432</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-hairline">
            <span className="text-mid-gray">Cache & Bus Tier</span>
            <span className="font-semibold text-ink">Redis @ 140.245.194.172:6379 (With In-Memory Fallback)</span>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-mid-gray">Local Docker Container Daemon</span>
            <span className="font-semibold text-ink">None Required (Zero-Docker Native Host Execution)</span>
          </div>
        </div>
      </Card>
    </div>
  );
};
