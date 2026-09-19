import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";

import type { Category } from "@/lib/schema";

export const DEFAULT_CATEGORIES: Category[] = [
  { category_id: 11, code: "EQ_CONTRA", label: "Contra Fund", asset_class: "EQUITY" },
  { category_id: 9, code: "EQ_DIVIDEND_YIELD", label: "Dividend Yield Fund", asset_class: "EQUITY" },
  { category_id: 5, code: "EQ_ELSS", label: "ELSS (Tax Saving)", asset_class: "EQUITY" },
  { category_id: 14, code: "EQ_ETF", label: "Equity ETF", asset_class: "EQUITY" },
  { category_id: 4, code: "EQ_FLEXI_CAP", label: "Flexi Cap", asset_class: "EQUITY" },
  { category_id: 8, code: "EQ_FOCUSED", label: "Focused Fund", asset_class: "EQUITY" },
  { category_id: 13, code: "EQ_INDEX", label: "Index Fund", asset_class: "EQUITY" },
  { category_id: 3, code: "EQ_LARGE_CAP", label: "Large Cap", asset_class: "EQUITY" },
  { category_id: 7, code: "EQ_LARGE_MID_CAP", label: "Large & Mid Cap Fund", asset_class: "EQUITY" },
  { category_id: 2, code: "EQ_MID_CAP", label: "Mid Cap", asset_class: "EQUITY" },
  { category_id: 6, code: "EQ_MULTI_CAP", label: "Multi Cap Fund", asset_class: "EQUITY" },
  { category_id: 12, code: "EQ_SECTORAL_THEMATIC", label: "Sectoral / Thematic Fund", asset_class: "EQUITY" },
  { category_id: 1, code: "EQ_SMALL_CAP", label: "Small Cap", asset_class: "EQUITY" },
  { category_id: 10, code: "EQ_VALUE", label: "Value Fund", asset_class: "EQUITY" },
];

export function useScreener() {
  const [searchParams, setSearchParams] = useSearchParams();

  const categoryId = searchParams.get("category_id")
    ? parseInt(searchParams.get("category_id")!, 10)
    : undefined;
  const sort = searchParams.get("sort") || "composite";
  const direction = searchParams.get("direction") || "desc";

  const setCategory = (catId?: number) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (catId) next.set("category_id", catId.toString());
      else next.delete("category_id");
      return next;
    });
  };

  const setSorting = (newSort: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (next.get("sort") === newSort) {
        next.set("direction", next.get("direction") === "asc" ? "desc" : "asc");
      } else {
        next.set("sort", newSort);
        next.set("direction", "desc");
      }
      return next;
    });
  };

  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: api.getCategories,
    initialData: DEFAULT_CATEGORIES,
    staleTime: 1000 * 60 * 60 * 24, // 24 hours
  });

  const screenerQuery = useQuery({
    queryKey: ["screener", categoryId, sort, direction],
    queryFn: () => api.getScreener({ categoryId, sort, direction }),
  });

  const matrixQuery = useQuery({
    queryKey: ["matrix", categoryId],
    queryFn: () => api.getMatrix(categoryId),
  });

  return {
    categoryId,
    sort,
    direction,
    setCategory,
    setSorting,
    categories: categoriesQuery.data || [],
    funds: screenerQuery.data || [],
    matrixData: matrixQuery.data || [],
    isLoading: screenerQuery.isLoading,
    isError: screenerQuery.isError,
    error: screenerQuery.error,
    refetch: screenerQuery.refetch,
  };
}
