import FacilityDirectory, { type SP } from "@/components/FacilityDirectory";

export default async function StateFacilities({ params, searchParams }: { params: Promise<{ code: string }>; searchParams: Promise<SP> }) {
  const { code } = await params;
  return <FacilityDirectory code={code} sp={await searchParams} />;
}
