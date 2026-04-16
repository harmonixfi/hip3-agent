import { getClosedPositions } from "@/lib/api";
import ClosedPositionsClient from "@/components/ClosedPositionsClient";

export const dynamic = "force-dynamic";

export default async function ClosedPositionsPage() {
  let closedPositions;
  let error: string | null = null;

  try {
    closedPositions = await getClosedPositions();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch closed positions";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Closed Positions</h1>

      {error || !closedPositions ? (
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load closed positions</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
        </div>
      ) : closedPositions.length === 0 ? (
        <div className="card">
          <p className="text-gray-500">No closed positions yet.</p>
        </div>
      ) : (
        <ClosedPositionsClient closedPositions={closedPositions} />
      )}
    </div>
  );
}
