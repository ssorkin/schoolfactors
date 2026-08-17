// Client-side CSV download for any table: build rows, get a file.
// Values are quoted per RFC 4180; null/undefined become empty cells (a blank
// can mean "suppressed at source" — it is never written as 0).
export function downloadCsv(filename, headers, rows) {
  const esc = (v) => {
    if (v == null) return '';
    const s = String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const text = [headers, ...rows].map((r) => r.map(esc).join(',')).join('\n') + '\n';
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
