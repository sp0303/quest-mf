import React from "react";

export interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className }) => {
  return (
    <div
      className={`animate-pulse rounded-2xl bg-hairline/70 ${className || "h-4 w-full"}`}
      aria-hidden="true"
    />
  );
};
