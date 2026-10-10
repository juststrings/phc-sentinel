import type { Metadata } from "next";
import FacilityDirectory, { type SP } from "@/components/FacilityDirectory";

export const metadata: Metadata = { title: "Facilities" };

/** Every public PHC in every covered state; filter by state to narrow it. */
export default async function AllFacilities({ searchParams }: { searchParams: Promise<SP> }) {
  return <FacilityDirectory sp={await searchParams} />;
}
