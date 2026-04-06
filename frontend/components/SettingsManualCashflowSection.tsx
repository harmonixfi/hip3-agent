"use client";

import { useCallback, useState } from "react";
import ManualCashflowForm from "@/components/ManualCashflowForm";
import ManualCashflowsTable from "@/components/ManualCashflowsTable";

export default function SettingsManualCashflowSection() {
  const [refreshKey, setRefreshKey] = useState(0);
  const onSuccess = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  return (
    <div className="space-y-6">
      <ManualCashflowForm onSuccess={onSuccess} />
      <ManualCashflowsTable refreshKey={refreshKey} />
    </div>
  );
}
