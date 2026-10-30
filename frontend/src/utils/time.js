// Parsing timecode HH:MM:SS | MM:SS | SS (opsional pecahan detik). Mengembalikan detik atau null.
export function parseTimecode(value) {
  const s = String(value ?? "").trim().replace(",", ".");
  if (!s) return null;
  const parts = s.split(":");
  if (parts.length > 3) return null;
  for (const p of parts.slice(0, -1)) if (!/^\d{1,4}$/.test(p)) return null;
  if (!/^\d{1,5}(\.\d{1,3})?$/.test(parts[parts.length - 1])) return null;
  const nums = parts.map(Number);
  if (parts.length >= 2 && nums[nums.length - 1] >= 60) return null;
  if (parts.length === 3 && nums[1] >= 60) return null;
  return nums.reduce((acc, n) => acc * 60 + n, 0);
}

export function formatTimecode(seconds) {
  const t = Math.max(0, Math.floor(seconds || 0));
  const h = String(Math.floor(t / 3600)).padStart(2, "0");
  const m = String(Math.floor((t % 3600) / 60)).padStart(2, "0");
  const s = String(t % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}
