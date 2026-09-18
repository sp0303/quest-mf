import React from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "./Button";
import { Card } from "./Card";

export interface ErrorCardProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorCard: React.FC<ErrorCardProps> = ({
  title = "An error occurred",
  message,
  onRetry,
  className,
}) => {
  return (
    <Card className={`p-6 border-ember/20 bg-ember/5 text-ink ${className || ""}`}>
      <div className="flex items-start gap-4">
        <div className="p-2 rounded-xl bg-ember/10 text-ember">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <p className="mt-1 text-xs text-mid-gray">{message}</p>
          {onRetry && (
            <div className="mt-4">
              <Button variant="secondary" size="sm" onClick={onRetry}>
                Try Again
              </Button>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};
