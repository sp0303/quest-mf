import React from "react";
import { clsx } from "clsx";

interface NumberCellProps {
  value: number | null | undefined;
  isPercent?: boolean;
  decimals?: number;
  showSign?: boolean;
  className?: string;
}

export const NumberCell: React.FC<NumberCellProps> = ({
  value,
  isPercent = false,
  decimals = 2,
  showSign = true,
  className,
}) => {
  if (value === null || value === undefined || isNaN(value)) {
    return <span className="text-mid-gray">—</span>;
  }

  const numVal = isPercent ? value * 100 : value;
  const isPositive = numVal > 0;
  const isNegative = numVal < 0;

  const formatted = Math.abs(numVal).toFixed(decimals);

  return (
    <span
      className={clsx(
        "tabular-nums font-medium text-right inline-flex items-center gap-0.5 justify-end",
        isNegative ? "text-ember" : "text-ink",
        className
      )}
    >
      {isPositive && showSign && <span className="text-[10px]">▲ +</span>}
      {isNegative && <span className="text-[10px]">▼ −</span>}
      {!isPositive && !isNegative && showSign && <span></span>}
      {formatted}
      {isPercent ? "%" : ""}
    </span>
  );
};
