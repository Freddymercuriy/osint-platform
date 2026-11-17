/**
 * ECharts — faqat kerakli qismlar (tree-shaking). Bu modul `components/charts/EChart.tsx` ichida dinamik
 * import qilinadi, shuning uchun grafik kutubxonasi alohida bo'lakda va faqat dashboard ochilganda yuklanadi.
 */
import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

echarts.use([
  BarChart, LineChart, HeatmapChart,
  GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, VisualMapComponent, AriaComponent,
  SVGRenderer,
]);

export default echarts;
export type { EChartsType } from "echarts/core";
