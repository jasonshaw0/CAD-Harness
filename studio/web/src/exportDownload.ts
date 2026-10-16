import { zipSync } from 'fflate';

export type ExportFormat = 'step' | 'stl';
export type PreparedDownload = { filename: string; blob: Blob };

export async function prepareExportDownload(
  files: string[], format: ExportFormat, archiveName: string, fileUrl: (file: string) => string,
): Promise<PreparedDownload> {
  const prefix = `project/exports/${format}/`;
  const paths = files.filter(file => file.startsWith(prefix) && file.endsWith(`.${format}`)).sort();
  if (!paths.length) throw new Error(`The export finished without any ${format.toUpperCase()} files. Try exporting again.`);
  const entries = await Promise.all(paths.map(async file => {
    const filename = file.slice(prefix.length);
    if (filename.includes('/') || filename.includes('\\') || filename === `.${format}`) {
      throw new Error('The export returned an invalid filename.');
    }
    const response = await fetch(fileUrl(file));
    if (!response.ok) throw new Error(`Could not download ${filename} (HTTP ${response.status}). Try exporting again.`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (!bytes.length) throw new Error(`The exported file ${filename} is empty.`);
    return [filename, bytes] as const;
  }));
  if (entries.length === 1) {
    return { filename: entries[0][0], blob: new Blob([entries[0][1]], { type: 'application/octet-stream' }) };
  }
  // Store the verified bytes unchanged; compression is unnecessary for delivery.
  const archive = zipSync(Object.fromEntries(entries), { level: 0 });
  return { filename: archiveName, blob: new Blob([new Uint8Array(archive)], { type: 'application/zip' }) };
}

export function saveExportDownload({ filename, blob }: PreparedDownload) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.hidden = true;
  document.body.append(link);
  link.click(); link.remove();
  // Chrome must be allowed to consume the Blob before its URL is released.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
