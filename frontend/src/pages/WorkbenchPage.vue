<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Sortable, { type SortableEvent } from 'sortablejs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, post, put } from '../api/client'
import CaptureReview from '../components/CaptureReview.vue'
import MetricCard from '../components/MetricCard.vue'
import SummaryChart from '../components/SummaryChart.vue'
import { useWorkbenchStore } from '../stores/workbench'
import type { Hotspot, ReportDocument, ReportSlide, Run } from '../types'

const route = useRoute()
const store = useWorkbenchStore()
const projectId = computed(() => String(route.params.projectId))
const activePage = ref('overview')
const model = ref<Record<string, any>>({})
const mesh = ref<Record<string, any>>({})
const components = ref<any[]>([])
const materials = ref<any[]>([])
const properties = ref<any[]>([])
const boundary = ref<Record<string, any[]>>({ loads: [], constraints: [], connections: [] })
const subcases = ref<any[]>([])
const resultIndex = ref<Record<string, any[]>>({ subcases: [], simulations: [], result_types: [] })
const hotspots = ref<Hotspot[]>([])
const selectedHotspot = ref<Hotspot | null>(null)
const hotspotDialog = ref(false)
const report = ref<ReportDocument | null>(null)
const activeSlide = ref(0)
const reportList = ref<HTMLElement | null>(null)
const filter = ref('')
const hotspotKind = ref('all')
const classification = ref('all')
const pageLoading = ref(false)

const runId = computed(() => store.run?.id)
const filteredHotspots = computed(() => hotspots.value.filter((item) =>
  (hotspotKind.value === 'all' || item.result_kind === hotspotKind.value) &&
  (classification.value === 'all' || item.classification === classification.value) &&
  (!filter.value || `${item.component_name} ${item.entity_id} ${item.subcase}`.toLowerCase().includes(filter.value.toLowerCase())),
))

const menuGroups = [
  {
    category: '📌 概览与控制',
    items: [
      ['overview', '项目概览', '01', '📊'],
      ['run', 'Run 概览与 DAG', '02', '⚡'],
    ]
  },
  {
    category: '🔍 模型与物理场',
    items: [
      ['model', '模型信息', '03', '📦'],
      ['mesh', '网格信息', '04', '🕸'],
      ['materials', '材料与属性', '05', '🧪'],
      ['boundary', '边界条件', '06', '⚓'],
      ['subcases', '子工况', '07', '📋'],
    ]
  },
  {
    category: '🎯 结果与成果',
    items: [
      ['hotspots', '结果热点', '08', '🔥'],
      ['report', '工程报告', '09', '📄'],
    ]
  }
]

const menu = menuGroups.flatMap((g) => g.items)

onMounted(async () => {
  await store.loadProject(projectId.value)
  store.connectEvents(projectId.value)
  await loadPage('overview')
})

watch(() => store.run?.status, async () => {
  if (store.run?.status === 'completed') await loadPage(activePage.value)
})

async function loadPage(page: string) {
  activePage.value = page
  if (!runId.value) return
  pageLoading.value = true
  try {
    if (['overview', 'model'].includes(page)) {
      [model.value, components.value] = await Promise.all([
        api<Record<string, any>>(`/api/v1/runs/${runId.value}/model-summary`), api<any[]>(`/api/v1/runs/${runId.value}/components`),
      ])
    }
    if (['overview', 'mesh'].includes(page)) mesh.value = await api<Record<string, any>>(`/api/v1/runs/${runId.value}/mesh-summary`)
    if (page === 'materials') [materials.value, properties.value] = await Promise.all([api<any[]>(`/api/v1/runs/${runId.value}/materials`), api<any[]>(`/api/v1/runs/${runId.value}/properties`)])
    if (page === 'boundary') boundary.value = await api<Record<string, any[]>>(`/api/v1/runs/${runId.value}/boundary-conditions`)
    if (page === 'subcases') [subcases.value, resultIndex.value] = await Promise.all([api<any[]>(`/api/v1/runs/${runId.value}/subcases`), api<Record<string, any[]>>(`/api/v1/runs/${runId.value}/result-index`)])
    if (['overview', 'hotspots'].includes(page)) hotspots.value = await api<Hotspot[]>(`/api/v1/runs/${runId.value}/hotspots`)
    if (page === 'report') {
      try { report.value = await api(`/api/v1/runs/${runId.value}/report`) }
      catch { report.value = await post(`/api/v1/runs/${runId.value}/report/generate-default`) }
      await nextTick()
      if (reportList.value && report.value) {
        Sortable.create(reportList.value, {
          animation: 150,
          onEnd: ({ oldIndex, newIndex }: SortableEvent) => {
            if (oldIndex == null || newIndex == null || !report.value) return
            const [slide] = report.value.slides.splice(oldIndex, 1)
            report.value.slides.splice(newIndex, 0, slide)
            activeSlide.value = newIndex
            saveReport(false)
          },
        })
      }
    }
  } catch (reason) {
    ElMessage.warning(reason instanceof Error ? reason.message : String(reason))
  } fontally: { pageLoading.value = false }
}

async function controlRun(action: string) {
  if (!runId.value) return
  await post(`/api/v1/runs/${runId.value}/${action}`)
  await store.loadProject(projectId.value)
}

async function rerunProject() {
  try {
    await ElMessageBox.confirm(
      '将重新读取当前 FEM/H3D 并接受最新文件指纹。上一次 Run 的结果、截图和报告会保留在历史记录中。',
      '重新运行分析',
      { confirmButtonText: '创建并运行', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  const rerun = await post<Run>(`/api/v1/projects/${projectId.value}/rerun`)
  await store.loadProject(projectId.value, rerun.id)
  await loadPage('run')
  ElMessage.success(`RUN ${String(rerun.run_no).padStart(3, '0')} 已开始`)
}

async function selectRun(runId: string) {
  await store.selectRun(runId)
  await loadPage(activePage.value)
}

async function openHotspot(item: Hotspot) {
  selectedHotspot.value = await api(`/api/v1/hotspots/${item.id}`)
  hotspotDialog.value = true
}

async function reloadHotspot() {
  if (selectedHotspot.value) selectedHotspot.value = await api(`/api/v1/hotspots/${selectedHotspot.value.id}`)
  if (runId.value) hotspots.value = await api<Hotspot[]>(`/api/v1/runs/${runId.value}/hotspots`)
}

async function saveReport(showMessage = true) {
  if (!runId.value || !report.value) return
  report.value = await put(`/api/v1/runs/${runId.value}/report`, { document: report.value })
  if (showMessage) ElMessage.success('报告草稿已保存')
}

function addSlide() {
  if (!report.value) return
  report.value.slides.push({ id: `slide-${Date.now()}`, title: '新页面', layout: 'title-content', elements: [{ type: 'text', text: '填写工程内容', x: .8, y: 1.4, w: 11.7, h: 4.8 }], notes: '' })
  activeSlide.value = report.value.slides.length - 1
}

function duplicateSlide() {
  if (!report.value) return
  const source = report.value.slides[activeSlide.value]
  const copy = structuredClone(source)
  copy.id = `slide-${Date.now()}`
  copy.title += '（副本）'
  report.value.slides.splice(activeSlide.value + 1, 0, copy)
  activeSlide.value += 1
}

function removeSlide() {
  if (!report.value || report.value.slides.length <= 1) return
  report.value.slides.splice(activeSlide.value, 1)
  activeSlide.value = Math.min(activeSlide.value, report.value.slides.length - 1)
}

async function exportPptx() {
  if (!runId.value) return
  await saveReport(false)
  const exported = await post<{ download_url: string }>(`/api/v1/runs/${runId.value}/report/export-pptx`)
  window.location.href = exported.download_url
  ElMessage.success('PPTX 已生成')
}

function csvDownload() {
  const rows = [['rank', 'kind', 'subcase', 'component', 'entity', 'value', 'unit'], ...filteredHotspots.value.map((h) => [h.rank, h.result_kind, h.subcase, h.component_name, h.entity_id, h.value, h.unit])]
  const blob = new Blob(['\ufeff' + rows.map((row) => row.join(',')).join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'hotspots.csv'; link.click(); URL.revokeObjectURL(link.href)
}

function source(kind: string) { return store.project?.sources?.find((item) => item.source_type === kind) }
function percent(current: number, total: number) { return total ? Math.round(current * 100 / total) : 0 }

function getTaskStatusClass(taskType: string) {
  const task = store.run?.tasks.find((t) => t.task_type === taskType)
  return task ? `task-${task.status}` : 'task-pending'
}

function getTaskStatusText(taskType: string) {
  const task = store.run?.tasks.find((t) => t.task_type === taskType)
  if (!task) return '等待中'
  if (task.status === 'completed') return '✔ 已完成'
  if (task.status === 'running') return '⚙ 运行中'
  if (task.status === 'failed') return '✖ 失败'
  return '⏳ 排队'
}
</script>

<template>
  <div class="workbench-shell">
    <aside>
      <router-link to="/projects" class="brand">
        <span>CR</span>
        <strong>CAE REPORT</strong>
      </router-link>
      <div class="project-identity">
        <small>{{ store.project?.code || 'PRJ-UNASSIGNED' }}</small>
        <h1>{{ store.project?.name || '加载中…' }}</h1>
        <p>{{ store.project?.analysis_type }} · {{ store.project?.unit_system }}</p>
      </div>

      <nav aria-label="结果工作台" class="nav-groups">
        <div v-for="group in menuGroups" :key="group.category" class="nav-group">
          <div class="nav-category">{{ group.category }}</div>
          <button
            v-for="item in group.items"
            :key="item[0]"
            :class="{ active: activePage === item[0] }"
            @click="loadPage(item[0])"
          >
            <span class="icon">{{ item[3] }}</span>
            <span class="text">{{ item[1] }}</span>
            <span class="num">{{ item[2] }}</span>
          </button>
        </div>
      </nav>

      <footer>
        <div><i :class="{ online: store.connected }"></i>{{ store.connected ? '实时事件已连接' : '事件连接中' }}</div>
        <p>Server 是唯一 SQLite 状态源</p>
      </footer>
    </aside>

    <main v-loading="store.loading || pageLoading">
      <header class="topbar">
        <div>
          <p>RUN {{ String(store.run?.run_no ?? 0).padStart(3, '0') }}</p>
          <h2>{{ menu.find((item) => item[0] === activePage)?.[1] }}</h2>
        </div>
        <div class="run-state">
          <el-select
            :model-value="store.selectedRunId"
            aria-label="Run 历史"
            style="width: 245px"
            @change="selectRun"
          >
            <el-option
              v-for="item in store.project?.runs"
              :key="item.id"
              :label="`RUN ${String(item.run_no).padStart(3, '0')} · ${item.name} · ${item.status}`"
              :value="item.id"
            />
          </el-select>
          <el-button type="primary" plain @click="rerunProject">重新运行</el-button>
          <span :class="`run-pill status-${store.run?.status}`">{{ store.run?.status || 'no run' }}</span>
          <el-progress type="circle" :width="46" :stroke-width="5" :percentage="store.run?.progress ?? 0" />
        </div>
      </header>

      <section v-if="store.error" class="error-panel">{{ store.error }}</section>

      <section v-else-if="activePage === 'overview'" class="content overview">
        <div class="metrics six">
          <metric-card label="节点" :value="model.node_count ?? '—'" />
          <metric-card label="单元" :value="model.element_count ?? '—'" />
          <metric-card label="Component" :value="model.component_count ?? '—'" />
          <metric-card label="Property" :value="model.property_count ?? '—'" />
          <metric-card label="Material" :value="model.material_count ?? '—'" />
          <metric-card label="热点" :value="hotspots.length" :detail="`${hotspots.filter((h) => h.result_kind === 'stress').length} 应力 / ${hotspots.filter((h) => h.result_kind === 'displacement').length} 位移`" />
        </div>
        <div class="grid two">
          <section class="panel source-panel">
            <div class="panel-heading"><h3>分析输入</h3><span>仅引用</span></div>
            <article v-for="kind in ['fem', 'h3d']" :key="kind">
              <strong>{{ kind.toUpperCase() }}</strong><div><b>{{ source(kind)?.filename || '—' }}</b><small>{{ source(kind)?.absolute_path }}</small></div><em :class="`availability-${source(kind)?.availability}`">{{ source(kind)?.availability }}</em>
            </article>
          </section>
          <section class="panel">
            <div class="panel-heading"><h3>最新 Run</h3><span>{{ store.run?.name }}</span></div>
            <div class="run-summary"><strong>{{ store.run?.progress ?? 0 }}%</strong><p>已完成 {{ store.run?.tasks.filter((t) => t.status === 'completed').length ?? 0 }} / {{ store.run?.tasks.length ?? 0 }} 项</p></div>
            <div class="button-row"><el-button type="primary" @click="controlRun('start')">启动</el-button><el-button @click="controlRun('pause')">暂停</el-button><el-button @click="controlRun('cancel')">取消</el-button><el-button type="warning" plain @click="rerunProject">重新运行</el-button></div>
          </section>
        </div>
        <div class="grid two">
          <summary-chart title="单元类型" :data="mesh.element_types ?? {}" />
          <summary-chart title="维度分布" :data="mesh.dimensions ?? {}" kind="pie" />
        </div>
        <section class="panel warning-panel"><div class="panel-heading"><h3>解析警告</h3><span>{{ model.warnings?.length ?? 0 }} 条</span></div><el-empty v-if="!model.warnings?.length" description="未发现解析警告" :image-size="54" /><div v-for="warning in model.warnings" v-else :key="warning.code">{{ warning.code }} · {{ warning.path }}</div></section>
      </section>

      <section v-else-if="activePage === 'run'" class="content">
        <div class="metrics four">
          <metric-card label="总体进度" :value="`${store.run?.progress ?? 0}%`" />
          <metric-card label="成功" :value="store.run?.tasks.filter((t) => t.status === 'completed').length ?? 0" />
          <metric-card label="执行中" :value="store.run?.tasks.filter((t) => t.status === 'running').length ?? 0" />
          <metric-card label="失败" :value="store.run?.tasks.filter((t) => t.status === 'failed').length ?? 0" />
        </div>

        <!-- DAG Flow Topology Section -->
        <section class="panel dag-panel">
          <div class="panel-heading">
            <h3>任务依赖拓扑 (DAG Pipeline Flow)</h3>
            <span>流向依赖关系 · 实时节点监控</span>
          </div>
          
          <div class="dag-graph">
            <div class="dag-phase">
              <div class="phase-title">Phase 1: FEM 解析</div>
              <div class="dag-node" :class="getTaskStatusClass('fem.model_summary')">
                <span class="node-icon">📦</span>
                <div class="node-info">
                  <strong>fem.model_summary</strong>
                  <small>{{ getTaskStatusText('fem.model_summary') }}</small>
                </div>
              </div>
              <div class="dag-node" :class="getTaskStatusClass('fem.mesh_summary')">
                <span class="node-icon">🕸</span>
                <div class="node-info">
                  <strong>fem.mesh_summary</strong>
                  <small>{{ getTaskStatusText('fem.mesh_summary') }}</small>
                </div>
              </div>
              <div class="dag-node" :class="getTaskStatusClass('fem.subcases')">
                <span class="node-icon">📋</span>
                <div class="node-info">
                  <strong>fem.subcases</strong>
                  <small>{{ getTaskStatusText('fem.subcases') }}</small>
                </div>
              </div>
            </div>

            <div class="dag-arrow">➔</div>

            <div class="dag-phase">
              <div class="phase-title">Phase 2: H3D & 热点提取</div>
              <div class="dag-node" :class="getTaskStatusClass('h3d.result_index')">
                <span class="node-icon">🔍</span>
                <div class="node-info">
                  <strong>h3d.result_index</strong>
                  <small>{{ getTaskStatusText('h3d.result_index') }}</small>
                </div>
              </div>
              <div class="dag-node" :class="getTaskStatusClass('result.stress_hotspots')">
                <span class="node-icon">🔥</span>
                <div class="node-info">
                  <strong>result.stress_hotspots</strong>
                  <small>{{ getTaskStatusText('result.stress_hotspots') }}</small>
                </div>
              </div>
              <div class="dag-node" :class="getTaskStatusClass('result.displacement_hotspots')">
                <span class="node-icon">📐</span>
                <div class="node-info">
                  <strong>result.displacement_hotspots</strong>
                  <small>{{ getTaskStatusText('result.displacement_hotspots') }}</small>
                </div>
              </div>
            </div>

            <div class="dag-arrow">➔</div>

            <div class="dag-phase">
              <div class="phase-title">Phase 3: 截图与报告</div>
              <div class="dag-node" :class="getTaskStatusClass('capture.standard_views')">
                <span class="node-icon">📷</span>
                <div class="node-info">
                  <strong>capture.standard_views</strong>
                  <small>{{ getTaskStatusText('capture.standard_views') }}</small>
                </div>
              </div>
              <div class="dag-node" :class="getTaskStatusClass('report.prepare')">
                <span class="node-icon">📄</span>
                <div class="node-info">
                  <strong>report.prepare</strong>
                  <small>{{ getTaskStatusText('report.prepare') }}</small>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-heading">
            <h3>任务列表与阶段进度</h3>
            <div class="button-row">
              <el-button size="small" type="primary" @click="controlRun('start')">启动</el-button>
              <el-button size="small" @click="controlRun('pause')">暂停</el-button>
              <el-button size="small" @click="controlRun('resume')">恢复</el-button>
              <el-button size="small" @click="controlRun('retry-failed')">重试失败项</el-button>
            </div>
          </div>
          <div class="task-list">
            <article v-for="task in store.run?.tasks" :key="task.id">
              <span class="task-state" :class="`task-${task.status}`"></span>
              <div>
                <strong>{{ task.task_type }}</strong>
                <small>{{ task.progress_message || '等待执行' }}</small>
              </div>
              <el-progress :percentage="percent(task.progress_current, task.progress_total)" :status="task.status === 'failed' ? 'exception' : task.status === 'completed' ? 'success' : undefined" />
            </article>
          </div>
        </section>

        <section class="panel"><div class="panel-heading"><h3>输入快照</h3><span>新 Run 不覆盖历史结果</span></div><pre>{{ JSON.stringify(store.run?.input_snapshot, null, 2) }}</pre></section>
      </section>

      <section v-else-if="activePage === 'model'" class="content">
        <div class="metrics six"><metric-card label="节点" :value="model.node_count ?? 0" /><metric-card label="单元" :value="model.element_count ?? 0" /><metric-card label="Component" :value="model.component_count ?? 0" /><metric-card label="INCLUDE" :value="model.include_count ?? 0" /><metric-card label="一维" :value="model.element_dimensions?.['1'] ?? 0" /><metric-card label="三维" :value="model.element_dimensions?.['3'] ?? 0" /></div>
        <section class="panel"><div class="panel-heading"><h3>Component</h3><el-input v-model="filter" placeholder="搜索 Component" clearable style="width:260px" /></div><el-table :data="components.filter((c) => !filter || c.name.toLowerCase().includes(filter.toLowerCase()))" stripe><el-table-column prop="id" label="ID" sortable width="100" /><el-table-column prop="name" label="名称" sortable /><el-table-column prop="property_id" label="Property" sortable /><el-table-column prop="element_count" label="单元数" sortable /></el-table></section>
        <div class="grid two"><section class="panel"><div class="panel-heading"><h3>包围盒</h3></div><pre>{{ JSON.stringify(model.bounding_box, null, 2) }}</pre></section><section class="panel"><div class="panel-heading"><h3>未引用实体</h3></div><pre>{{ JSON.stringify(model.unreferenced, null, 2) }}</pre></section></div>
      </section>

      <section v-else-if="activePage === 'mesh'" class="content">
        <div class="grid two"><summary-chart title="单元类型统计" :data="mesh.element_types ?? {}" /><summary-chart title="维度统计" :data="mesh.dimensions ?? {}" kind="pie" /></div>
        <div class="metrics four"><metric-card label="平均边长" :value="mesh.average_edge_length?.toFixed(3) ?? '—'" /><metric-card label="三角形" :value="mesh.triangle_count ?? 0" /><metric-card label="四边形" :value="mesh.quad_count ?? 0" /><metric-card label="孤立节点" :value="mesh.orphan_node_count ?? 0" /></div>
        <section class="panel"><div class="panel-heading"><h3>实体与刚性单元</h3></div><el-descriptions :column="3" border><el-descriptions-item label="实体类型">{{ JSON.stringify(mesh.solid_types ?? {}) }}</el-descriptions-item><el-descriptions-item label="RBE2">{{ mesh.rbe2_count ?? 0 }}</el-descriptions-item><el-descriptions-item label="RBE3">{{ mesh.rbe3_count ?? 0 }}</el-descriptions-item></el-descriptions></section>
      </section>

      <section v-else-if="activePage === 'materials'" class="content">
        <section class="panel"><div class="panel-heading"><h3>材料</h3><span>{{ materials.length }} 项</span></div><el-table :data="materials" stripe><el-table-column prop="id" label="ID" sortable /><el-table-column prop="type" label="类型" /><el-table-column prop="E" label="E" sortable /><el-table-column prop="nu" label="ν" /><el-table-column prop="rho" label="ρ" /><el-table-column prop="source_file" label="源文件" show-overflow-tooltip /></el-table></section>
        <section class="panel"><div class="panel-heading"><h3>属性</h3><span>{{ properties.length }} 项</span></div><el-table :data="properties" stripe><el-table-column prop="id" label="ID" sortable /><el-table-column prop="type" label="类型" /><el-table-column prop="material_ids" label="Material" /><el-table-column prop="thickness" label="壳厚" sortable /><el-table-column prop="line_no" label="行号" /></el-table></section>
      </section>

      <section v-else-if="activePage === 'boundary'" class="content">
        <div class="metrics four"><metric-card label="载荷" :value="boundary.loads.length" /><metric-card label="约束" :value="boundary.constraints.length" /><metric-card label="连接" :value="boundary.connections.length" /><metric-card label="合计" :value="boundary.loads.length + boundary.constraints.length + boundary.connections.length" /></div>
        <section v-for="kind in ['constraints', 'loads', 'connections']" :key="kind" class="panel"><div class="panel-heading"><h3>{{ { constraints: '约束', loads: '载荷', connections: '连接' }[kind] }}</h3><span>{{ boundary[kind]?.length ?? 0 }} 项</span></div><el-table :data="boundary[kind]" stripe><el-table-column prop="id" label="ID" sortable /><el-table-column prop="type" label="类型" sortable /><el-table-column prop="raw_fields" label="数值 / 引用" show-overflow-tooltip /><el-table-column prop="source_file" label="源文件" show-overflow-tooltip /><el-table-column prop="line_no" label="行号" width="90" /></el-table></section>
      </section>

      <section v-else-if="activePage === 'subcases'" class="content">
        <section class="panel"><div class="panel-heading"><h3>FEM 子工况</h3><span>{{ subcases.length }} 项</span></div><el-table :data="subcases" stripe><el-table-column prop="id" label="ID" /><el-table-column prop="name" label="名称" /><el-table-column prop="references" label="LOAD / SPC / METHOD / NLPARM" /><el-table-column prop="source_file" label="源文件" show-overflow-tooltip /></el-table></section>
        <section class="panel"><div class="panel-heading"><h3>H3D 结果索引</h3><span>绑定 H3D 指纹</span></div><div class="result-types"><article v-for="result in resultIndex.result_types" :key="result.id"><strong>{{ result.name }}</strong><p>{{ result.components?.join(' · ') }}</p><span>{{ result.unit }}</span></article></div></section>
      </section>

      <section v-else-if="activePage === 'hotspots'" class="content">
        <section class="panel"><div class="panel-heading hotspot-toolbar"><div><h3>热点审查</h3><span>{{ filteredHotspots.length }} / {{ hotspots.length }}</span></div><div><el-input v-model="filter" placeholder="搜索 component / entity / subcase" clearable style="width:280px" /><el-select v-model="hotspotKind" style="width:130px"><el-option label="全部结果" value="all" /><el-option label="应力" value="stress" /><el-option label="位移" value="displacement" /></el-select><el-select v-model="classification" style="width:140px"><el-option v-for="value in ['all','valid','singularity','contact_singularity','mesh_issue','boundary_issue','ignore','unknown']" :key="value" :label="value" :value="value" /></el-select><el-button type="primary" plain @click="csvDownload">导出 CSV</el-button></div></div>
          <el-table :data="filteredHotspots" stripe @row-dblclick="openHotspot"><el-table-column prop="rank" label="#" sortable width="65" /><el-table-column prop="result_kind" label="结果" width="100" /><el-table-column prop="subcase" label="子工况" /><el-table-column prop="component_name" label="Component" sortable /><el-table-column label="Entity"><template #default="scope">{{ scope.row.entity_type }} {{ scope.row.entity_id }}</template></el-table-column><el-table-column label="数值" sortable><template #default="scope"><strong>{{ scope.row.value }}</strong> {{ scope.row.unit }}</template></el-table-column><el-table-column prop="classification" label="分类" /><el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" @click="openHotspot(scope.row)">审查</el-button></template></el-table-column></el-table>
        </section>
      </section>

      <section v-else-if="activePage === 'report' && report" class="content report-workspace">
        <div class="report-toolbar"><div><el-button type="primary" @click="saveReport()">保存草稿</el-button><el-button @click="addSlide">添加页面</el-button><el-button @click="duplicateSlide">复制</el-button><el-button type="danger" plain @click="removeSlide">删除</el-button></div><el-button type="success" @click="exportPptx">导出 PPTX</el-button></div>
        <div class="report-layout">
          <div ref="reportList" class="slide-list"><button v-for="(slide, index) in report.slides" :key="slide.id" :class="{ active: index === activeSlide }" @click="activeSlide = index"><span>{{ index + 1 }}</span><div class="slide-mini"><strong>{{ slide.title }}</strong><small>{{ slide.layout }}</small></div></button></div>
          <div class="slide-editor">
            <div class="slide-canvas">
              <input v-model="report.slides[activeSlide].title" class="slide-title" aria-label="页面标题" />
              <div v-for="(element, index) in report.slides[activeSlide].elements" :key="index" class="slide-element" :style="{ left: `${element.x / 13.333 * 100}%`, top: `${element.y / 7.5 * 100}%`, width: `${element.w / 13.333 * 100}%`, height: `${element.h / 7.5 * 100}%` }">
                <textarea v-if="element.type === 'text'" v-model="element.text" aria-label="文本内容"></textarea><img v-else-if="element.type === 'image' && element.src" :src="element.src" alt="报告素材" />
              </div>
              <span class="slide-number">{{ activeSlide + 1 }}</span>
            </div>
            <el-input v-model="report.slides[activeSlide].notes" type="textarea" :rows="3" placeholder="演讲者备注" />
          </div>
        </div>
      </section>
    </main>

    <el-dialog v-model="hotspotDialog" width="88%" top="4vh" destroy-on-close>
      <template #header><div class="dialog-title"><div><small>{{ selectedHotspot?.subcase }} · {{ selectedHotspot?.result_kind }}</small><h3>{{ selectedHotspot?.component_name }} / {{ selectedHotspot?.entity_type }} {{ selectedHotspot?.entity_id }}</h3></div><strong>{{ selectedHotspot?.value }} {{ selectedHotspot?.unit }}</strong></div></template>
      <div v-if="selectedHotspot" class="hotspot-detail"><el-descriptions :column="4" border><el-descriptions-item label="排名">#{{ selectedHotspot.rank }}</el-descriptions-item><el-descriptions-item label="坐标">{{ selectedHotspot.coordinate?.join(', ') }}</el-descriptions-item><el-descriptions-item label="分类"><el-select v-model="selectedHotspot.classification" size="small"><el-option v-for="value in ['valid','singularity','contact_singularity','mesh_issue','boundary_issue','ignore','unknown']" :key="value" :label="value" :value="value" /></el-select></el-descriptions-item><el-descriptions-item label="审核">{{ selectedHotspot.review_status }}</el-descriptions-item></el-descriptions><capture-review :captures="selectedHotspot.captures ?? []" @changed="reloadHotspot" /></div>
    </el-dialog>
  </div>
</template>

<style scoped>
.workbench-shell { min-height: 100vh; display: grid; grid-template-columns: 248px 1fr; background: #f1f5f9; }
aside { position: sticky; top: 0; height: 100vh; display: flex; flex-direction: column; background: #0f172a; color: #cbd5e1; padding: 20px 14px; overflow: hidden; }
.brand { display: flex; align-items: center; gap: 10px; color: white; text-decoration: none; padding: 0 8px 18px; border-bottom: 1px solid #ffffff18; }
.brand span { display: grid; place-items: center; width: 36px; height: 36px; background: #0284c7; border-radius: 8px; font-size: 13px; font-weight: 800; }
.brand strong { letter-spacing: .09em; font-size: 14px; }
.project-identity { padding: 16px 8px 12px; }
.project-identity small { color: #38bdf8; font-weight: 700; letter-spacing: .08em; font-family: var(--font-mono); }
.project-identity h1 { margin: 6px 0; font-size: 16px; line-height: 1.35; color: white; }
.project-identity p { margin: 0; color: #94a3b8; font-size: 11px; }

.nav-groups { display: flex; flex-direction: column; gap: 14px; overflow-y: auto; padding-right: 2px; }
.nav-category { font-size: 11px; font-weight: 700; color: #64748b; margin: 4px 6px 2px; text-transform: uppercase; letter-spacing: 0.05em; }
.nav-groups button { display: flex; align-items: center; gap: 10px; width: 100%; border: 0; border-radius: 8px; background: transparent; color: #94a3b8; text-align: left; padding: 9px 10px; cursor: pointer; transition: all 0.15s ease; }
.nav-groups button .icon { font-size: 14px; }
.nav-groups button .text { font-size: 13px; flex: 1; }
.nav-groups button .num { color: #475569; font-family: var(--font-mono); font-size: 10px; }
.nav-groups button:hover { background: #ffffff0e; color: white; }
.nav-groups button.active { background: #0284c7; color: white; font-weight: 600; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3); }
.nav-groups button.active .num { color: #e0f2fe; }

aside footer { margin-top: auto; padding: 14px 8px 0; border-top: 1px solid #ffffff18; color: #64748b; font-size: 11px; }
aside footer div { display: flex; align-items: center; gap: 7px; }
aside footer i { width: 7px; height: 7px; border-radius: 50%; background: #f59e0b; }
aside footer i.online { background: #10b981; box-shadow: 0 0 8px #10b981; }

main { min-width: 0; }
.topbar { height: 80px; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; background: white; border-bottom: 1px solid #e2e8f0; }
.topbar p { margin: 0 0 2px; color: #0284c7; font-size: 11px; font-weight: 700; letter-spacing: .1em; font-family: var(--font-mono); }
.topbar h2 { margin: 0; color: #0f172a; font-size: 22px; font-weight: 700; }
.run-state { display: flex; align-items: center; gap: 14px; }
.run-pill { padding: 5px 12px; border-radius: 999px; background: #e0f2fe; color: #0284c7; font-size: 11px; text-transform: uppercase; font-weight: 700; }

.content { display: grid; gap: 16px; padding: 22px 28px 44px; }
.metrics { display: grid; gap: 12px; }
.metrics.six { grid-template-columns: repeat(6, 1fr); }
.metrics.four { grid-template-columns: repeat(4, 1fr); }
.grid { display: grid; gap: 16px; }
.grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }

/* DAG Topology Graph */
.dag-panel { background: white; border-radius: var(--radius-md); border: 1px solid var(--border-color); }
.dag-graph { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; overflow-x: auto; }
.dag-phase { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 200px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
.phase-title { font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px dashed #cbd5e1; padding-bottom: 6px; margin-bottom: 2px; }
.dag-node { display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; transition: all 0.2s ease; }
.dag-node.task-completed { border-color: #10b981; background: #f0fdf4; }
.dag-node.task-running { border-color: #0284c7; background: #f0f9ff; box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15); }
.dag-node.task-failed { border-color: #ef4444; background: #fef2f2; }
.dag-node.task-pending { opacity: 0.6; }
.node-icon { font-size: 16px; }
.node-info strong { display: block; font-size: 12px; color: #0f172a; }
.node-info small { font-size: 10px; color: #64748b; }
.dag-arrow { color: #94a3b8; font-size: 18px; font-weight: bold; }

.panel { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; box-shadow: var(--shadow-sm); }
.panel-heading { display: flex; align-items: center; justify-content: space-between; min-height: 30px; margin-bottom: 14px; }
.panel-heading h3 { margin: 0; color: #0f172a; font-size: 16px; font-weight: 600; }
.panel-heading span { color: #64748b; font-size: 12px; }
.source-panel article { display: grid; grid-template-columns: 48px 1fr auto; align-items: center; gap: 12px; padding: 12px 0; border-top: 1px solid #f1f5f9; }
.source-panel article > strong { color: #0284c7; font-size: 12px; }
.source-panel article div { min-width: 0; }
.source-panel article b, .source-panel article small { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.source-panel article b { font-size: 13px; }
.source-panel article small { color: #64748b; font-size: 10px; font-family: var(--font-mono); }
.source-panel article em { font-style: normal; font-size: 10px; color: #059669; }
.run-summary { display: flex; align-items: baseline; gap: 15px; padding: 20px 0; }
.run-summary strong { font-size: 44px; color: #0284c7; font-family: var(--font-mono); }
.run-summary p { color: #64748b; }
.button-row { display: flex; gap: 6px; }
.warning-panel { min-height: 130px; }
.error-panel { margin: 30px; padding: 20px; border-radius: 8px; background: #fef2f2; color: #b91c1c; }

.task-list { display: grid; }
.task-list article { display: grid; grid-template-columns: 14px minmax(220px, 1fr) minmax(280px, 2fr); gap: 12px; align-items: center; padding: 12px 4px; border-top: 1px solid #f1f5f9; }
.task-list article div strong, .task-list article div small { display: block; }
.task-list article div strong { color: #1e293b; font-size: 13px; }
.task-list article div small { color: #64748b; font-size: 11px; }
.task-state { width: 9px; height: 9px; border-radius: 50%; background: #cbd5e1; }
.task-running { background: #0284c7; box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.2); }
.task-completed { background: #10b981; }
.task-failed { background: #ef4444; }

pre { max-height: 310px; overflow: auto; padding: 14px; background: #f8fafc; color: #334155; border-radius: 7px; border: 1px solid #e2e8f0; font-family: var(--font-mono); font-size: 11px; }

.result-types { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }
.result-types article { border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; }
.result-types strong { color: #0f172a; }
.result-types p { color: #64748b; }
.result-types span { color: #0284c7; font-size: 12px; font-family: var(--font-mono); }
.hotspot-toolbar > div { display: flex; align-items: center; gap: 8px; }
.hotspot-toolbar > div:first-child { display: block; }

.dialog-title { display: flex; justify-content: space-between; padding-right: 22px; }
.dialog-title small { color: #0284c7; }
.dialog-title h3 { margin: 4px 0 0; }
.dialog-title > strong { color: #ea580c; font-size: 24px; font-family: var(--font-mono); }
.hotspot-detail { display: grid; gap: 14px; }

.report-workspace { padding: 16px 20px 30px; }
.report-toolbar { display: flex; justify-content: space-between; margin-bottom: 12px; }
.report-layout { display: grid; grid-template-columns: 210px minmax(680px, 1fr); gap: 16px; min-height: calc(100vh - 170px); }
.slide-list { display: flex; flex-direction: column; gap: 7px; overflow: auto; }
.slide-list button { display: grid; grid-template-columns: 22px 1fr; align-items: center; gap: 7px; border: 1px solid #cbd5e1; border-radius: 7px; background: white; padding: 7px; cursor: grab; transition: all 0.15s ease; }
.slide-list button.active { border-color: #0284c7; box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.2); }
.slide-list button > span { color: #64748b; font-size: 11px; }
.slide-mini { aspect-ratio: 16 / 9; display: flex; flex-direction: column; justify-content: center; background: #f8fafc; padding: 8px; text-align: left; overflow: hidden; border: 1px dashed #cbd5e1; }
.slide-mini strong { color: #0f172a; font-size: 10px; }
.slide-mini small { color: #94a3b8; font-size: 8px; }
.slide-editor { display: grid; align-content: start; gap: 12px; }
.slide-canvas { position: relative; width: min(100%, 1066px); aspect-ratio: 16 / 9; margin: 0 auto; background: white; box-shadow: var(--shadow-lg); overflow: hidden; border-radius: 4px; border: 1px solid #cbd5e1; }
.slide-title { position: absolute; top: 4.3%; left: 5%; width: 90%; border: 0; outline: 0; background: transparent; color: #0f172a; font-size: clamp(20px, 2.2vw, 32px); font-weight: 700; }
.slide-element { position: absolute; overflow: hidden; }
.slide-element textarea { width: 100%; height: 100%; resize: none; border: 1px dashed transparent; outline: none; background: transparent; color: #334155; font-size: clamp(11px, 1.2vw, 18px); }
.slide-element textarea:focus { border-color: #0284c7; }
.slide-element img { width: 100%; height: 100%; object-fit: contain; }
.slide-number { position: absolute; right: 2%; bottom: 2%; color: #94a3b8; font-size: 10px; font-family: var(--font-mono); }

@media (max-width: 1280px) { .metrics.six { grid-template-columns: repeat(3, 1fr); } }
</style>

