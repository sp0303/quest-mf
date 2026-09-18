import React from "react";
import type { Category } from "@/lib/schema";

export interface ScreenerFiltersProps {
  categories: Category[];
  selectedCategoryId?: number;
  onSelectCategory: (id?: number) => void;
}

export const ScreenerFilters: React.FC<ScreenerFiltersProps> = ({
  categories,
  selectedCategoryId,
  onSelectCategory,
}) => {
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Category filter">
      <button
        type="button"
        onClick={() => onSelectCategory(undefined)}
        className={`px-3 py-1.5 text-xs font-medium rounded-2xl transition-colors ${
          selectedCategoryId === undefined
            ? "bg-ink text-paper"
            : "bg-canvas text-mid-gray hover:text-ink"
        }`}
      >
        All Categories
      </button>
      {categories.map((c) => (
        <button
          key={c.category_id}
          type="button"
          onClick={() => onSelectCategory(c.category_id)}
          className={`px-3 py-1.5 text-xs font-medium rounded-2xl transition-colors ${
            selectedCategoryId === c.category_id
              ? "bg-ink text-paper"
              : "bg-canvas text-mid-gray hover:text-ink"
          }`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
};
