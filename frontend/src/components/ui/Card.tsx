import React from "react";
import { clsx } from "clsx";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ children, className, ...props }) => {
  return (
    <div
      className={clsx(
        "bg-paper rounded-3xl border border-hairline shadow-subtle p-5 transition-shadow",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
