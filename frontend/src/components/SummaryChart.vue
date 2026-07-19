<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent])
const props = defineProps<{ title: string; data: Record<string, number>; kind?: 'bar' | 'pie' }>()
const option = computed(() => props.kind === 'pie' ? ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{ type: 'pie', radius: ['38%', '68%'], center: ['50%', '45%'], data: Object.entries(props.data).map(([name, value]) => ({ name, value })) }],
}) : ({
  tooltip: { trigger: 'axis' },
  grid: { left: 42, right: 16, top: 16, bottom: 42 },
  xAxis: { type: 'category', data: Object.keys(props.data), axisLabel: { rotate: 24 } },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: Object.values(props.data), itemStyle: { color: '#21869b', borderRadius: [4, 4, 0, 0] } }],
}))
</script>

<template>
  <section class="chart-card">
    <h3>{{ title }}</h3>
    <v-chart :option="option" autoresize class="chart" />
  </section>
</template>

<style scoped>
.chart-card { background: white; border: 1px solid #dce5eb; border-radius: 10px; padding: 16px; }
.chart-card h3 { margin: 0 0 8px; color: #1b374c; font-size: 15px; }
.chart { height: 280px; }
</style>

