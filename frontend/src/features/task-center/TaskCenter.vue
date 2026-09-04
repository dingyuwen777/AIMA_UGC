<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

import TaskProgressBar from '../../shared/TaskProgressBar.vue'
import { formatDateTime } from '../../shared/domain/beijingTime'
import AimaIcon from '../../shared/ui/AimaIcon.vue'
import { useTaskCenterStore, type TaskCenterItem } from './store'

const store = useTaskCenterStore()

/** 将任务终态映射到既有进度条语义色，不把颜色作为唯一状态表达。 */
function progressTone(item: TaskCenterItem): 'primary' | 'success' | 'warning' | 'danger' {
  if (item.status === 'failed') return 'danger'
  if (item.status === 'partial_failed' || item.status === 'partial_success') return 'warning'
  if (!item.active && item.status === 'succeeded') return 'success'
  return 'primary'
}

/** 将任务来源映射为用户可理解的业务分类名称。 */
function kindLabel(kind: TaskCenterItem['kind']): string {
  if (kind === 'analysis') return 'AI 打标'
  if (kind === 'collection') return '采集运行'
  return '数据导出'
}

/** Escape 关闭任务中心，保持抽屉与其它全局浮层一致的键盘退出行为。 */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && store.open) store.closeCenter()
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  store.startPolling()
  void store.refresh()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  store.stopPolling()
})
</script>

<template>
  <div class="task-center">
    <button
      class="task-center-trigger"
      type="button"
      aria-label="任务中心"
      :aria-expanded="store.open"
      @click="store.openCenter()"
    >
      <AimaIcon
        name="task"
        :size="16"
      />
      <span>任务中心</span>
      <b
        v-if="store.activeCount"
        class="task-center-badge"
        :aria-label="`${store.activeCount} 个进行中的任务`"
      >{{ store.activeCount > 99 ? '99+' : store.activeCount }}</b>
    </button>

    <Teleport to="body">
      <div
        v-if="store.open"
        class="task-center-layer"
      >
        <button
          class="task-center-backdrop"
          type="button"
          aria-label="关闭任务中心"
          @click="store.closeCenter()"
        />
        <aside
          class="task-center-drawer"
          aria-label="任务中心"
        >
          <header class="task-center-header">
            <div>
              <strong>任务中心</strong>
              <span>跨页面查看后台任务；详细业务管理仍在对应页面完成。</span>
            </div>
            <button
              class="task-center-close"
              type="button"
              aria-label="关闭任务中心"
              @click="store.closeCenter()"
            >
              <AimaIcon
                name="close"
                :size="18"
              />
            </button>
          </header>

          <div
            v-if="store.warning"
            class="task-center-warning"
            role="alert"
          >
            {{ store.warning }}
          </div>

          <div
            v-if="store.loading && !store.items.length"
            class="task-center-empty"
          >
            正在读取任务状态…
          </div>

          <template v-else>
            <section class="task-center-section">
              <header class="task-center-section-heading">
                <strong>进行中</strong>
                <span>{{ store.activeCount }} 个</span>
              </header>
              <div
                v-if="!store.activeItems.length"
                class="task-center-empty"
              >
                当前没有进行中的后台任务。
              </div>
              <article
                v-for="item in store.activeItems"
                :key="item.key"
                class="task-card task-card--active"
              >
                <header class="task-card-heading">
                  <div>
                    <span class="task-kind">{{ kindLabel(item.kind) }}</span>
                    <strong>{{ item.title }}</strong>
                  </div>
                  <span
                    class="task-status"
                    :class="`task-status--${item.status}`"
                  >{{ item.statusLabel }}</span>
                </header>
                <p>{{ item.subtitle }}</p>
                <TaskProgressBar
                  compact
                  :label="`${item.title} 进度`"
                  :value="item.progress"
                  :detail="item.progressDetail"
                  :tone="progressTone(item)"
                />
                <footer class="task-card-footer">
                  <span>{{ formatDateTime(item.createdAt) }}</span>
                  <div class="task-card-actions">
                    <button
                      v-if="item.cancelable"
                      type="button"
                      :disabled="store.cancellingAnalysisRunId === item.sourceId"
                      @click="store.cancelAnalysisRun(item.sourceId)"
                    >
                      {{ store.cancellingAnalysisRunId === item.sourceId ? '取消中…' : '取消' }}
                    </button>
                    <RouterLink
                      :to="item.href"
                      @click="store.closeCenter()"
                    >
                      查看
                    </RouterLink>
                  </div>
                </footer>
              </article>
            </section>

            <section class="task-center-section task-center-section--recent">
              <header class="task-center-section-heading">
                <strong>最近完成</strong>
                <span>最多显示 12 条</span>
              </header>
              <div
                v-if="!store.recentItems.length"
                class="task-center-empty"
              >
                暂无已完成任务。
              </div>
              <article
                v-for="item in store.recentItems"
                :key="item.key"
                class="task-card"
              >
                <header class="task-card-heading">
                  <div>
                    <span class="task-kind">{{ kindLabel(item.kind) }}</span>
                    <strong>{{ item.title }}</strong>
                  </div>
                  <span
                    class="task-status"
                    :class="`task-status--${item.status}`"
                  >{{ item.statusLabel }}</span>
                </header>
                <p>{{ item.subtitle }}</p>
                <div class="task-result">
                  <span>{{ item.progressDetail }}</span>
                  <span v-if="item.errorCode">{{ item.errorCode }}</span>
                </div>
                <footer class="task-card-footer">
                  <span>{{ formatDateTime(item.finishedAt ?? item.createdAt) }}</span>
                  <RouterLink
                    :to="item.href"
                    @click="store.closeCenter()"
                  >
                    查看详情
                  </RouterLink>
                </footer>
              </article>
            </section>
          </template>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.task-center { position: relative; }
.task-center-trigger {
  position: relative;
  display: inline-flex;
  height: 32px;
  align-items: center;
  gap: 6px;
  padding: 0 9px;
  border: 1px solid var(--aima-border);
  border-radius: 7px;
  color: var(--aima-text-secondary);
  background: var(--aima-surface);
  cursor: pointer;
  font-size: 11px;
}
.task-center-trigger:hover { border-color: #c7cdd8; color: var(--aima-text); }
.task-center-trigger:focus-visible,
.task-center-close:focus-visible,
.task-card-actions button:focus-visible,
.task-card-actions a:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: 2px; }
.task-center-badge {
  display: grid;
  min-width: 17px;
  height: 17px;
  place-items: center;
  padding: 0 4px;
  border-radius: 999px;
  color: #fff;
  background: var(--aima-primary);
  font-size: 9px;
  line-height: 1;
}
.task-center-layer { position: fixed; z-index: 240; inset: 0; }
.task-center-backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgb(19 27 43 / 24%); cursor: default; }
.task-center-drawer {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  width: min(540px, calc(100vw - 48px));
  height: 100vh;
  flex-direction: column;
  overflow-y: auto;
  background: #f8f9fb;
  box-shadow: -12px 0 36px rgb(23 32 49 / 16%);
}
.task-center-header {
  position: sticky;
  z-index: 1;
  top: 0;
  display: flex;
  min-height: 78px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--aima-border);
  background: rgb(255 255 255 / 96%);
}
.task-center-header div { display: grid; gap: 4px; }
.task-center-header strong { color: var(--aima-text); font-size: 17px; }
.task-center-header span { color: var(--aima-text-muted); font-size: 10px; }
.task-center-close { display: grid; width: 32px; height: 32px; flex: 0 0 auto; place-items: center; border: 0; border-radius: 6px; color: var(--aima-text-secondary); background: transparent; cursor: pointer; }
.task-center-close:hover { background: #f0f2f6; }
.task-center-warning { margin: 14px 18px 0; padding: 9px 11px; border: 1px solid #f3d59b; border-radius: 7px; color: #835600; background: #fff9ea; font-size: 10px; line-height: 1.5; }
.task-center-section { display: grid; gap: 10px; padding: 18px; }
.task-center-section--recent { padding-top: 4px; }
.task-center-section-heading { display: flex; align-items: center; justify-content: space-between; }
.task-center-section-heading strong { color: var(--aima-text); font-size: 13px; }
.task-center-section-heading span { color: var(--aima-text-muted); font-size: 10px; }
.task-center-empty { padding: 18px; border: 1px dashed var(--aima-border); border-radius: 8px; color: var(--aima-text-muted); background: #fff; font-size: 11px; text-align: center; }
.task-card { display: grid; gap: 9px; padding: 12px 13px; border: 1px solid var(--aima-border); border-radius: 9px; background: #fff; }
.task-card--active { border-color: #d9e6ff; box-shadow: 0 4px 14px rgb(37 99 235 / 5%); }
.task-card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.task-card-heading > div { display: grid; min-width: 0; gap: 3px; }
.task-card-heading strong { overflow: hidden; color: var(--aima-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.task-kind { color: var(--aima-text-muted); font-size: 9px; }
.task-status { flex: 0 0 auto; padding: 2px 7px; border-radius: 999px; color: #2563eb; background: #edf4ff; font-size: 9px; }
.task-status--succeeded { color: #12804b; background: #e9f9f1; }
.task-status--failed,
.task-status--partial_failed { color: #cf3440; background: #fff0f1; }
.task-status--partial_success { color: #a86100; background: #fff6e6; }
.task-status--cancelled { color: #697386; background: #f1f3f6; }
.task-card p { overflow: hidden; margin: 0; color: var(--aima-text-secondary); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.task-result { display: flex; min-width: 0; justify-content: space-between; gap: 12px; color: var(--aima-text-muted); font-size: 10px; }
.task-result span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-card-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--aima-text-muted); font-size: 9px; }
.task-card-actions { display: flex; align-items: center; gap: 9px; }
.task-card-actions button,
.task-card-actions a,
.task-card-footer > a { padding: 0; border: 0; color: var(--aima-primary); background: transparent; cursor: pointer; font-size: 10px; text-decoration: none; }
.task-card-actions button:disabled { cursor: wait; opacity: .55; }
</style>
