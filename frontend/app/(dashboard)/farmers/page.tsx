"use client";

import { useMemo, useState } from "react";
import { UserPlus } from "lucide-react";
import FarmerAnalyticsDrawer from "@/app/components/FarmerAnalyticsDrawer";
import FarmerQuickPanel from "@/app/components/FarmerQuickPanel";
import FarmersTable from "@/app/components/FarmersTable";
import CRDAFarmerInput from "@/app/components/CRDAFarmerInput";
import Modal from "@/app/components/Modal";
import PageTitle from "@/app/components/PageTitle";
import { useDelegation } from "@/app/context/DelegationProvider";
import { planReallocation } from "@/app/lib/reallocation";
import type { Farmer } from "@/types";

/** `null` = closed, `"new"` = registering, a Farmer = editing that farmer. */
type ModalState = null | "new" | Farmer;

export default function FarmersPage() {
  const { selected, farmers, facilities, upsertFarmer } = useDelegation();
  const [modal, setModal] = useState<ModalState>(null);
  const plan = useMemo(() => planReallocation(farmers, facilities), [farmers, facilities]);
  // Held by id so the drawer reflects edits saved from the modal.
  const [analyticsId, setAnalyticsId] = useState<string | null>(null);

  function handleSave(farmer: Farmer) {
    upsertFarmer(farmer);
    setModal(null);
  }

  const editing = modal !== null && modal !== "new" ? modal : null;
  const analyticsFarmer = farmers.find((f) => f.id === analyticsId) ?? null;

  return (
    <>
      <PageTitle
        title="Farmers"
        subtitle={`Multi-crop harvest, waste and income for farmers in ${selected.name}. Select a farmer for deep analytics.`}
        action={
          <button
            type="button"
            onClick={() => setModal("new")}
            className="inline-flex min-h-[40px] items-center gap-2 rounded-full bg-accent px-5 py-2 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg"
          >
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            Add Farmer
          </button>
        }
      />

      <FarmersTable
        farmers={farmers}
        delegationName={selected.name}
        onEdit={setModal}
        onSelect={(f) => setAnalyticsId(f.id)}
        renderExpanded={(f) => (
          <FarmerQuickPanel
            farmer={f}
            plan={plan}
            facilities={facilities}
            onEdit={setModal}
            onOpenFull={(farmer) => setAnalyticsId(farmer.id)}
          />
        )}
      />

      <FarmerAnalyticsDrawer
        farmer={analyticsFarmer}
        farmers={farmers}
        facilities={facilities}
        onClose={() => setAnalyticsId(null)}
        onEdit={(f) => {
          setAnalyticsId(null);
          setModal(f);
        }}
      />

      <Modal
        open={modal !== null}
        onClose={() => setModal(null)}
        title={editing ? "Edit Farmer" : "Add Farmer"}
      >
        <CRDAFarmerInput
          delegation={selected}
          editing={editing}
          onSave={handleSave}
          onCancelEdit={() => setModal(null)}
        />
      </Modal>
    </>
  );
}
