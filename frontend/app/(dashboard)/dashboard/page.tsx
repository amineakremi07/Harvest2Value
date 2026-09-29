"use client";

import { useState } from "react";
import Link from "next/link";
import { Activity, ArrowRight, UserPlus, Users, Warehouse, Wheat } from "lucide-react";
import OptimizationHero from "@/app/components/OptimizationHero";
import KpiCard from "@/app/components/KpiCard";
import CropDistributionCard from "@/app/components/CropDistributionCard";
import StorageRiskCard from "@/app/components/StorageRiskCard";
import FarmersTable from "@/app/components/FarmersTable";
import CRDAFarmerInput from "@/app/components/CRDAFarmerInput";
import Modal from "@/app/components/Modal";
import PageTitle from "@/app/components/PageTitle";
import { numberFormatter } from "@/app/components/styles";
import { useDelegation } from "@/app/context/DelegationProvider";
import { computeRegionStats } from "@/app/lib/regionStats";
import type { Farmer } from "@/types";

export default function DashboardPage() {
  const { selected, farmers, facilities, upsertFarmer } = useDelegation();
  const [addOpen, setAddOpen] = useState(false);
  const stats = computeRegionStats(farmers, facilities);

  function handleSave(farmer: Farmer) {
    upsertFarmer(farmer);
    setAddOpen(false);
  }

  return (
    <>
      <PageTitle
        title="Dashboard"
        subtitle={`${selected.name}, ${selected.governorate} — current period overview`}
        action={
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="inline-flex min-h-[40px] items-center gap-2 rounded-full bg-accent px-5 py-2 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg"
          >
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            Quick Add Farmer
          </button>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={Users} label="Total Farmers" value={numberFormatter.format(stats.farmerCount)} />
        <KpiCard
          icon={Wheat}
          label="Harvest Volume"
          value={numberFormatter.format(stats.totalYieldKg / 1000)}
          suffix="tons"
        />
        <KpiCard
          icon={Warehouse}
          label="Storage Fill"
          value={(100 - stats.availablePct).toFixed(0)}
          suffix="%"
          accentColor={stats.availablePct < 15 ? "var(--danger)" : undefined}
        />
        <KpiCard
          icon={Activity}
          label="Regional Risk Score"
          value={String(stats.healthScore)}
          suffix="/ 100"
          accentColor={stats.healthScore < 60 ? "var(--danger)" : undefined}
        />
      </div>

      <OptimizationHero />

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-5">
          <CropDistributionCard farmers={farmers} />
        </div>
        <div className="col-span-12 lg:col-span-7">
          <StorageRiskCard facilities={facilities} delegationId={selected.id} />
        </div>
      </div>

      <FarmersTable farmers={farmers} delegationName={selected.name} />
      <Link
        href="/farmers"
        className="inline-flex items-center gap-1.5 rounded-lg text-sm font-semibold text-accent-text outline-none hover:underline focus-visible:ring-2 focus-visible:ring-accent"
      >
        Manage farmers <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Quick Add Farmer">
        <CRDAFarmerInput
          delegation={selected}
          onSave={handleSave}
        />
      </Modal>
    </>
  );
}
