import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";

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
    isLoading: screenerQuery.isLoading || categoriesQuery.isLoading,
    isError: screenerQuery.isError,
    error: screenerQuery.error,
    refetch: screenerQuery.refetch,
  };
}
