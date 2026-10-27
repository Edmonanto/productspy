/** Products picked for side-by-side comparison — a per-browser convenience (localStorage). */
import { useCallback, useEffect, useState } from "react";

const KEY = "ps.compare";
const EVENT = "productspy:compare";
export const COMPARE_MAX = 5;

function read(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, COMPARE_MAX) : [];
  } catch {
    return [];
  }
}

function write(ids: string[]) {
  try { localStorage.setItem(KEY, JSON.stringify(ids)); } catch {}
  window.dispatchEvent(new Event(EVENT));
}

export function useCompare() {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const sync = () => setIds(read());
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(EVENT, sync); window.removeEventListener("storage", sync); };
  }, []);
  const toggle = useCallback((id: string) => {
    const cur = read();
    write(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id].slice(-COMPARE_MAX));
  }, []);
  const clear = useCallback(() => write([]), []);
  return { ids, toggle, clear, has: (id: string) => ids.includes(id) };
}
