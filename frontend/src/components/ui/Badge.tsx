import React from "react";
import { clsx } from "clsx";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "solid" | "soft" | "outline" | "ember";
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "soft",
  className,
  ...props
}) => {
  const variants = {
    solid: "bg-ink text-paper",
    soft: "bg-canvas text-ink border border-hairline",
    outline: "border border-hairline bg-transparent text-mid-gray",
    ember: "bg-ember/10 text-ember border border-ember/20",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-2xl px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
