"use client";

import { motion } from "framer-motion";

interface HealthGaugeProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

export function HealthGauge({ score, size = 140, strokeWidth = 10, label = "Compliance Score" }: HealthGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75;
  const offset = arcLength - (score / 100) * arcLength;

  const color =
    score >= 80 ? "#34D399" :
    score >= 50 ? "#F59E0B" :
    "#F87171";

  const glowColor =
    score >= 80 ? "rgba(52, 211, 153, 0.6)" :
    score >= 50 ? "rgba(245, 158, 11, 0.6)" :
    "rgba(248, 113, 113, 0.6)";

  return (
    <div className="relative flex flex-col items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-[135deg]">
        {/* Background arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={arcLength}
          className="text-muted/20"
        />
        {/* Score arc with glow */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={arcLength}
          style={{ filter: `drop-shadow(0 0 6px ${glowColor})` }}
          initial={{ strokeDashoffset: arcLength }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="text-3xl font-bold tabular-nums font-mono-num"
          style={{ color, filter: `drop-shadow(0 0 8px ${glowColor})` }}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
        >
          {Math.round(score)}
        </motion.span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      </div>
    </div>
  );
}
