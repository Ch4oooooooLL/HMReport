<script setup lang="ts">
import { onMounted } from 'vue'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()
onMounted(() => store.loadProjects())
</script>

<template>
  <main class="projects-page">
    <header>
      <div class="brand-mark">CR</div>
      <div>
        <h1>CAE 结果分析与报告工作台</h1>
        <p>本地项目、结果审查与工程报告</p>
      </div>
    </header>
    <section class="project-panel">
      <div class="panel-title">
        <div><span>最近项目</span><small>{{ store.projects.length }} 个本地项目</small></div>
        <el-tag type="success" effect="plain">离线可用</el-tag>
      </div>
      <div v-if="store.projects.length" class="project-grid">
        <router-link v-for="project in store.projects" :key="project.id" :to="`/projects/${project.id}`" class="project-card">
          <div class="project-code">{{ project.code || '未编号' }}</div>
          <h2>{{ project.name }}</h2>
          <p>{{ project.analysis_type }} · {{ project.solver }} · {{ project.unit_system }}</p>
          <footer><span :class="`status status-${project.status}`">{{ project.status }}</span><strong>进入工作台 →</strong></footer>
        </router-link>
      </div>
      <el-empty v-else description="请在桌面项目管理器中创建项目" />
    </section>
  </main>
</template>

<style scoped>
.projects-page { min-height: 100vh; background: #edf2f5; padding: 48px max(32px, calc((100vw - 1180px) / 2)); }
header { display: flex; align-items: center; gap: 18px; margin-bottom: 36px; }
.brand-mark { display: grid; place-items: center; width: 58px; height: 58px; border-radius: 12px; background: #176b87; color: white; font-weight: 700; letter-spacing: .08em; box-shadow: 0 10px 24px #176b8730; }
h1 { margin: 0; font-size: 28px; color: #173248; } header p { margin: 5px 0 0; color: #6b7f8e; }
.project-panel { background: white; border: 1px solid #d8e1e7; border-radius: 14px; padding: 24px; box-shadow: 0 12px 40px rgba(34, 59, 76, .07); }
.panel-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }.panel-title span { display: block; font-size: 19px; font-weight: 600; color: #173248; }.panel-title small { color: #82929e; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 14px; }
.project-card { display: block; padding: 20px; border: 1px solid #dbe4e9; border-radius: 10px; color: inherit; text-decoration: none; transition: .18s ease; }
.project-card:hover { transform: translateY(-2px); border-color: #4a99a9; box-shadow: 0 10px 22px #274d6514; }
.project-code { color: #26859a; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }.project-card h2 { margin: 9px 0; color: #20384b; font-size: 19px; }.project-card p { min-height: 38px; color: #738490; font-size: 13px; }
.project-card footer { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; }.project-card footer strong { color: #176b87; font-size: 13px; }
.status { padding: 4px 8px; border-radius: 999px; background: #e9f4ef; color: #287657; font-size: 11px; }
</style>

