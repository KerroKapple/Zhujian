/* ECharts「zhujian」工程蓝主题 */
import * as echarts from 'echarts'

export const ZHUJIAN_THEME = 'zhujian'

// 工程蓝色板（浅色卡片内使用）
const palette = [
  '#1f6feb',
  '#2da44e',
  '#d29922',
  '#cf222e',
  '#16335c',
  '#2dd4bf',
  '#8957e5',
  '#0f274d',
]

const theme = {
  color: palette,
  backgroundColor: 'transparent',
  textStyle: { color: '#5b6675', fontFamily: 'inherit' },
  title: {
    textStyle: { color: '#1f2733', fontWeight: 600 },
    subtextStyle: { color: '#8a93a3' },
  },
  legend: { textStyle: { color: '#5b6675' } },
  grid: { left: 12, right: 16, top: 32, bottom: 12, containLabel: true },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#e3e8ef' } },
    axisTick: { show: false },
    axisLabel: { color: '#8a93a3' },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#8a93a3' },
    splitLine: { lineStyle: { color: '#eef1f5' } },
  },
  line: { smooth: true, symbol: 'circle', symbolSize: 6 },
  bar: { itemStyle: { borderRadius: [4, 4, 0, 0] } },
  tooltip: {
    backgroundColor: '#fff',
    borderColor: '#e3e8ef',
    textStyle: { color: '#1f2733' },
    extraCssText: 'box-shadow:0 6px 24px rgba(20,40,80,.12);border-radius:10px;',
  },
}

echarts.registerTheme(ZHUJIAN_THEME, theme)
