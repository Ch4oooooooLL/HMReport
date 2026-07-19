<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, post } from '../api/client'
import type { Capture } from '../types'

const props = defineProps<{ captures: Capture[] }>()
const emit = defineEmits<{ changed: [] }>()
const active = ref(0)
const current = computed(() => props.captures[active.value])
const version = computed(() => current.value?.versions.find((item) => item.is_current) ?? current.value?.versions[0])
const restoring = ref(false)

async function action(name: 'approve' | 'reject' | 'recapture') {
  if (!current.value) return
  await post(`/api/v1/captures/${current.value.id}/${name}`, { note: '' })
  ElMessage.success(name === 'approve' ? '已批准图片' : name === 'reject' ? '已否决图片' : '已提交重拍')
  emit('changed')
}

async function restore(bringToFront: boolean) {
  if (!current.value || restoring.value) return
  restoring.value = true
  try {
    const queued = await post<{ restore_request_id: string }>(
      `/api/v1/captures/${current.value.id}/restore-view`,
      { bring_to_front: bringToFront },
    )
    const deadline = Date.now() + 120_000
    while (Date.now() < deadline) {
      const request = await api<{ status: string; missing: string[] }>(
        `/api/v1/view-restores/${queued.restore_request_id}`,
      )
      if (request.status === 'exact') {
        ElMessage.success(bringToFront ? '视图已恢复并显示在 HyperView 中' : '视图已在后台精确恢复')
        return
      }
      if (request.status === 'partial') {
        ElMessage.warning(`视图已部分恢复，未恢复字段：${request.missing.join('、') || '未知'}`)
        return
      }
      if (request.status === 'failed') {
        ElMessage.error('视图恢复失败，请查看诊断日志')
        return
      }
      await new Promise((resolve) => window.setTimeout(resolve, 300))
    }
    ElMessage.warning('视图恢复仍在执行，可稍后重试')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '视图恢复失败')
  } finally {
    restoring.value = false
  }
}
</script>

<template>
  <div v-if="current" class="capture-review">
    <div class="capture-tabs">
      <button v-for="(capture, index) in captures" :key="capture.id" :class="{ active: index === active }" @click="active = index">
        {{ capture.view_name }}
        <span :class="`status-${capture.review_status}`">{{ capture.review_status }}</span>
      </button>
    </div>
    <div class="capture-stage">
      <img v-if="version" :src="`/api/v1/capture-versions/${version.id}/image`" :alt="current.name" />
    </div>
    <div class="capture-actions">
      <el-button type="success" @click="action('approve')">批准</el-button>
      <el-button type="danger" plain @click="action('reject')">否决</el-button>
      <el-button @click="action('recapture')">重拍</el-button>
      <el-button :loading="restoring" :disabled="restoring" @click="restore(false)">恢复到后台</el-button>
      <el-button type="primary" plain :loading="restoring" :disabled="restoring" @click="restore(true)">恢复并显示 HyperView</el-button>
      <span class="version">共 {{ current.versions.length }} 个版本</span>
    </div>
  </div>
</template>

<style scoped>
.capture-review { display: grid; gap: 12px; }
.capture-tabs { display: flex; gap: 6px; overflow: auto; padding-bottom: 4px; }
.capture-tabs button { border: 1px solid #cfdae1; border-radius: 7px; background: #f7f9fb; color: #435b6d; padding: 8px 10px; white-space: nowrap; cursor: pointer; }
.capture-tabs button.active { background: #e7f3f5; border-color: #21869b; color: #155c6b; }
.capture-tabs span { margin-left: 7px; font-size: 10px; text-transform: uppercase; }
.capture-stage { min-height: 320px; display: grid; place-items: center; background: #152534; border-radius: 9px; overflow: hidden; }
.capture-stage img { width: 100%; max-height: 58vh; object-fit: contain; }
.capture-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.version { margin-left: auto; color: #7a8b97; font-size: 12px; }
.status-approved { color: #21865c; }.status-rejected { color: #c14c4c; }.status-pending { color: #a77019; }
</style>
