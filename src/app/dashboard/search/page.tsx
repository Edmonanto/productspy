"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { productsApi, Product } from "@/lib/api";
import ProductCard from "@/components/products/ProductCard";
import Topbar from "@/components/layout/Topbar";
import { Search as SearchIcon } from "lucide-react";

const GRID = "grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4";

function SearchResults() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const [draft, setDraft] = useState(q);

  useEffect(() => setDraft(q), [q]);

  // Keyed on the committed query only. /products/search spends a search from
  // the plan's quota — five a day on free — so it must never fire per
  // keystroke. Typing changes `draft`; only submitting changes the URL.
  const { data, isLoading, error } = useSWR(
    q ? ["search", q] : null,
    () => productsApi.search(q),
  );

  const products: Product[] = data?.products ?? [];

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = draft.trim();
    if (next && next !== q) router.push(`/dashboard/search?q=${encodeURIComponent(next)}`);
  };

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Search" />

      <div className="p-4 sm:p-6 space-y-6">
        <form onSubmit={submit} className="flex gap-2 max-w-xl">
          <div className="relative flex-1">
            <SearchIcon size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Search products by title…"
              aria-label="Search products"
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-sm rounded-lg pl-9 pr-3 py-2.5 focus:outline-none focus:border-violet-500 placeholder-zinc-600"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors disabled:opacity-40"
            disabled={!draft.trim()}
          >
            Search
          </button>
        </form>

        {/* Each search is billed against the plan quota, so say so up front. */}
        <p className="text-xs text-zinc-600">
          Each search counts against your plan&apos;s daily quota.
        </p>

        {!q && (
          <p className="text-sm text-zinc-500">
            Enter a term above to search the scored catalogue.
          </p>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-sm text-red-300">
            {(error as Error).message || "Search failed."}
          </div>
        )}

        {isLoading && (
          <div className={GRID}>
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl aspect-[3/4] animate-pulse" />
            ))}
          </div>
        )}

        {q && !isLoading && !error && (
          products.length > 0 ? (
            <>
              <p className="text-sm text-zinc-500">
                <span className="text-white font-bold">{data?.total ?? products.length}</span>{" "}
                result{(data?.total ?? products.length) === 1 ? "" : "s"} for &ldquo;{q}&rdquo;
              </p>
              <div className={GRID}>
                {products.map((p) => <ProductCard key={p.id} product={p} />)}
              </div>
            </>
          ) : (
            <p className="text-sm text-zinc-500">No products match &ldquo;{q}&rdquo;.</p>
          )
        )}
      </div>
    </div>
  );
}

export default function SearchPage() {
  // useSearchParams needs a Suspense boundary to stay statically renderable.
  return (
    <Suspense fallback={<div className="p-4 sm:p-6 text-sm text-zinc-500">Loading…</div>}>
      <SearchResults />
    </Suspense>
  );
}
