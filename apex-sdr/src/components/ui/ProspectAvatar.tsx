"use client";

import { cn } from "@/lib/utils";

interface ProspectAvatarProps {
  initials: string;
  color: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeMap = {
  sm: "w-7 h-7 text-xs",
  md: "w-8 h-8 text-xs",
  lg: "w-10 h-10 text-sm",
};

export function ProspectAvatar({
  initials,
  color,
  size = "md",
  className,
}: ProspectAvatarProps) {
  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center font-semibold flex-shrink-0 ring-1 ring-white/10",
        sizeMap[size],
        className
      )}
      style={{
        background: `${color}22`,
        color: color,
        border: `1px solid ${color}33`,
      }}
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}
