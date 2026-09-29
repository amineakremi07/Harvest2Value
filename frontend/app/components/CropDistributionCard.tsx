"use client";

import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { glassCard, numberFormatter } from "@/app/components/styles";
import { CROPS, CROP_COLORS, CROP_TYPES, type Farmer } from "@/types";

export default function CropDistributionCard({
  farmers,
  title = "Crop Distribution",
}: {
  farmers: Farmer[];
  title?: string;
}) {
  const { slices, totalKg } = useMemo(() => {
    const totals = CROP_TYPES.map((crop) => ({
      crop,
      label: CROPS[crop].label,
      kg: farmers.reduce(
        (sum, f) => sum + f.crops.filter((c) => c.crop === crop).reduce((s, c) => s + c.yieldKg, 0),
        0,
      ),
    })).filter((s) => s.kg > 0);
    return { slices: totals, totalKg: totals.reduce((s, t) => s + t.kg, 0) };
  }, [farmers]);

  return (
    <section aria-labelledby="crop-dist-title" className={glassCard}>
      <h2 id="crop-dist-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        {title}
      </h2>

      {totalKg === 0 ? (
        <p className="py-10 text-center text-sm text-text-secondary">No harvest recorded for this delegation.</p>
      ) : (
        <div className="flex flex-col items-center gap-4 sm:flex-row">
          <div
            className="relative h-[200px] w-[200px] shrink-0"
            role="img"
            aria-label={`Crop distribution: ${slices
              .map((s) => `${s.label} ${((s.kg / totalKg) * 100).toFixed(0)}%`)
              .join(", ")}`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="kg"
                  nameKey="label"
                  innerRadius={62}
                  outerRadius={92}
                  paddingAngle={2}
                  stroke="none"
                >
                  {slices.map((s) => (
                    <Cell key={s.crop} fill={CROP_COLORS[s.crop]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => `${numberFormatter.format(Number(value))} kg`}
                  contentStyle={{
                    background: "var(--card-surface)",
                    border: "1px solid var(--card-border)",
                    borderRadius: 12,
                    color: "var(--text-primary)",
                    fontSize: 12,
                  }}
                  itemStyle={{ color: "var(--text-primary)" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-2xl font-bold tabular-nums text-text-primary">
                {numberFormatter.format(totalKg / 1000)}
              </span>
              <span className="text-xs text-text-secondary">tons total</span>
            </div>
          </div>

          <ul className="w-full space-y-2">
            {slices.map((s) => (
              <li key={s.crop} className="flex items-center justify-between gap-3 text-sm">
                <span className="flex items-center gap-2 text-text-primary">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: CROP_COLORS[s.crop] }}
                    aria-hidden="true"
                  />
                  {s.label}
                </span>
                <span className="font-mono tabular-nums text-text-secondary">
                  {((s.kg / totalKg) * 100).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
