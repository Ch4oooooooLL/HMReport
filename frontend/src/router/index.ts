import { createRouter, createWebHistory } from 'vue-router'
import ProjectsPage from '../pages/ProjectsPage.vue'
import WorkbenchPage from '../pages/WorkbenchPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/projects' },
    { path: '/projects', component: ProjectsPage },
    { path: '/projects/:projectId', component: WorkbenchPage },
  ],
})

