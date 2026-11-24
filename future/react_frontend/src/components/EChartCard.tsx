import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface EChartCardProps {
  title: string;
  subtitle?: string;
  option: echarts.EChartsOption;
  height?: number;
  onItemClick?: (name: string) => void;
}

export const EChartCard: React.FC<EChartCardProps> = ({
  title,
  subtitle,
  option,
  height = 290,
  onItemClick,
}) => {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.setOption(option);

    if (onItemClick) {
      chart.on("click", (params: any) => {
        if (params && params.name) onItemClick(String(params.name));
      });
    }

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [option, onItemClick]);

  return (
    <div className="nexus-card p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-slate-100">{title}</h3>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        <span className="text-[11px] text-cyan-400/80 font-medium">Apache ECharts</span>
      </div>
      <div ref={ref} style={{ width: "100%", height }} />
    </div>
  );
};
