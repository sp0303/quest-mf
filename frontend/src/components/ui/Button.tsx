import React from "react";
import { clsx } from "clsx";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "secondary" | "outline" | "destructive";
  size?: "sm" | "md" | "lg";
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "default",
  size = "md",
  className,
  ...props
}) => {
  const base =
    "inline-flex items-center justify-center font-medium rounded-2xl transition-all focus:outline-none focus:ring-2 focus:ring-hairline disabled:opacity-50";

  const variants = {
    default: "bg-ink text-paper hover:bg-ink-soft",
    secondary: "bg-canvas text-ink hover:bg-surface-alt",
    outline: "border border-hairline bg-transparent text-ink hover:bg-canvas",
    destructive: "bg-ember text-paper hover:opacity-90",
  };

  const sizes = {
    sm: "text-xs px-3 py-1.5 h-8",
    md: "text-sm px-4 py-2 h-9",
    lg: "text-base px-5 py-2.5 h-11",
  };

  return (
    <button
      className={clsx(base, variants[variant], sizes[size], className)}
      {...props}
    >
      {children}
    </button>
  );
};
