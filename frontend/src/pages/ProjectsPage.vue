<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()
const searchQuery = ref('')
const selectedStatus = ref('all')

onMounted(() => store.loadProjects())

const filteredProjects = computed(() => {
  return store.projects.filter((p) => {
    const matchesSearch = !searchQuery.value ||
      p.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      (p.code && p.code.toLowerCase().includes(searchQuery.value.toLowerCase())) ||
      (p.solver && p.solver.toLowerCase().includes(searchQuery.value.toLowerCase()))
    
    const matchesStatus = selectedStatus.value === 'all' || p.status === selectedStatus.value
    return matchesSearch && matchesStatus
  })
})
</script>

<template>
  <main class="projects-page">
    <header class="brand-header">
      <div class="brand-logo">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
          <polyline points="2 17 12 22 22 17"></polyline>
          <polyline points="2 12 12 17 22 12"></polyline>
        </svg>
      </div>
      <div class="brand-info">
        <h1>CAE 结果分析与报告工作台</h1>
        <p>本地高效分析 · 自动热点提取 · PPT 工程报告生成</p>
      </div>
    </header>

    <section class="project-panel">
      <div class="panel-header">
        <div class="header-left">
          <h2>项目画廊</h2>
          <span class="count-badge">{{ filteredProjects.length }} / {{ store.projects.length }} 个工程项目</span>
        </div>
        
        <div class="header-actions">
          <el-input
            v-model="searchQuery"
            placeholder="搜索项目名称、编号或求解器..."
            clearable
            style="width: 280px"
          />
          
          <el-radio-group v-model="selectedStatus" size="default">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="completed">已完成</el-radio-button>
            <el-radio-button label="running">进行中</el-radio-button>
            <el-radio-button label="draft">草稿</el-radio-button>
          </el-radio-group>
          
          <el-tag type="success" effect="light" class="offline-tag">离线可用</el-tag>
        </div>
      </div>

      <div v-if="filteredProjects.length" class="project-grid">
        <router-link
          v-for="project in filteredProjects"
          :key="project.id"
          :to="`/projects/${project.id}`"
          class="project-card"
        >
          <div class="card-top">
            <span class="project-code">{{ project.code || 'PRJ-UNASSIGNED' }}</span>
            <span :class="`status-pill status-${project.status}`">{{ project.status }}</span>
          </div>

          <h3 class="project-title">{{ project.name }}</h3>
          
          <div class="project-meta">
            <span class="meta-item">求解器: {{ project.solver || 'OptiStruct' }}</span>
            <span class="meta-item">单位制: {{ project.unit_system || 'mm-N-MPa' }}</span>
            <span class="meta-item">类型: {{ project.analysis_type || '线性静力学' }}</span>
          </div>

          <div class="card-footer">
            <span class="enter-btn">进入工作台 →</span>
          </div>
        </router-link>
      </div>

      <el-empty v-else description="未找到符合条件的项目。请在桌面应用中创建新项目。" />
    </section>
  </main>
</template>

<style scoped>
.projects-page {
  min-height: 100vh;
  background: var(--bg-app);
  padding: 40px max(32px, calc((100vw - 1280px) / 2));
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.brand-logo {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
  color: white;
  box-shadow: 0 8px 20px rgba(2, 132, 199, 0.25);
}

.brand-info h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.brand-info p {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: 14px;
}

.project-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 28px;
  box-shadow: var(--shadow-md);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.count-badge {
  color: var(--text-muted);
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.offline-tag {
  font-weight: 600;
  border-radius: 999px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 18px;
}

.project-card {
  display: flex;
  flex-direction: column;
  padding: 22px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #ffffff;
  color: inherit;
  text-decoration: none;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: var(--shadow-sm);
}

.project-card:hover {
  transform: translateY(-4px);
  border-color: var(--primary);
  box-shadow: var(--shadow-lg);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.project-code {
  color: var(--primary);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.status-pill {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  background: #f1f5f9;
  color: var(--text-muted);
}

.status-completed { background: #ecfdf5; color: #059669; }
.status-running { background: #e0f2fe; color: #0284c7; }
.status-failed { background: #fef2f2; color: #dc2626; }
.status-draft { background: #f8fafc; color: #64748b; }

.project-title {
  margin: 0 0 14px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.35;
}

.project-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}

.meta-item {
  font-size: 12px;
  color: var(--text-muted);
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}

.card-footer {
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px dashed var(--border-color);
  display: flex;
  justify-content: flex-end;
}

.enter-btn {
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  transition: color 0.15s ease;
}

.project-card:hover .enter-btn {
  color: var(--primary-hover);
}
</style>



