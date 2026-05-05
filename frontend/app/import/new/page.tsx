import { backendRequest } from "@/lib/api/server";
import type { PdfListResponse } from "@/lib/api/types";
import { ImportWorkbench } from "@/components/import/ImportWorkbench";

export default async function NewImportPage() {
  const pdfs = await backendRequest<PdfListResponse>("/files/pdfs");

  return <ImportWorkbench files={pdfs.files} />;
}
