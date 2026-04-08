"use client";

import { useCallback, useState } from "react";
import ManualCashflowForm from "@/components/ManualCashflowForm";
import CashflowsTable from "@/components/CashflowsTable";

export default function SettingsManualCashflowSection() {
  const [refreshKey, setRefreshKey] = useState(0);
  const onSuccess = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  return (
    <div className="space-y-6">
      <ManualCashflowForm onSuccess={onSuccess} />
      <CashflowsTable refreshKey={refreshKey} />
    </div>
  );
}
