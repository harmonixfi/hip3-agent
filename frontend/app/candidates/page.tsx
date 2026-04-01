import { getCandidates } from "@/lib/api";
import CandidatesClient from "@/components/CandidatesClient";

export const revalidate = 0; // always fetch fresh on page load

export default async function CandidatesPage() {
  let data;
  let error: string | null = null;

  try {
    data = await getCandidates();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch candidates";
  }

  if (error || !data) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Candidates</h1>
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load candidates data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
          <p className="text-xs text-gray-600 mt-2">
            Run the export script or check the API connection.
          </p>
        </div>
      </div>
    );
  }

  const updatedAt = new Date(data.as_of).toLocaleString("en-US", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Candidates</h1>
        <span className="text-xs text-gray-500">Last updated: {updatedAt} ICT</span>
      </div>

      <div className="card">
        <CandidatesClient data={data} />
      </div>
    </div>
  );
}
