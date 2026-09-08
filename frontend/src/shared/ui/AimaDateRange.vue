<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import AimaButton from './AimaButton.vue'

const props = withDefaults(defineProps<{ from: string; to: string; label?: string }>(), { label: '发布时间范围' })
const emit = defineEmits<{ 'update:from': [value: string]; 'update:to': [value: string] }>()
const trigger = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const open = ref(false)
const draftFrom = ref('')
const draftTo = ref('')
const month = ref('')
const focused = ref('')
const position = ref({ left: '0px', top: '0px' })
const weekdays = ['一', '二', '三', '四', '五', '六', '日']

/** 以北京时间获取当天自然日，浏览器所在时区不改变筛选范围。 */
function today(): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  return ['year', 'month', 'day'].map((type) => parts.find((part) => part.type === type)?.value).join('-')
}

/** 日期运算使用 UTC 日历，避免夏令时或浏览器时区造成跨日偏差。 */
function shift(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

const monthLabel = computed(() => month.value ? `${Number(month.value.slice(0, 4))} 年 ${Number(month.value.slice(5, 7))} 月` : '')
const days = computed(() => {
  if (!month.value) return []
  const first = `${month.value}-01`
  const leading = (new Date(`${first}T00:00:00Z`).getUTCDay() + 6) % 7
  const last = new Date(`${first}T00:00:00Z`)
  last.setUTCMonth(last.getUTCMonth() + 1, 0)
  const count = last.getUTCDate()
  return Array.from({ length: Math.ceil((leading + count) / 7) * 7 }, (_, index) => {
    const day = index - leading + 1
    return day > 0 && day <= count ? `${month.value}-${String(day).padStart(2, '0')}` : null
  })
})

/** 打开时恢复已确认范围，并把面板放在视口内的触发器附近。 */
async function show(): Promise<void> {
  if (open.value) { panel.value?.hidePopover(); return }
  draftFrom.value = props.from
  draftTo.value = props.to
  focused.value = props.from || today()
  month.value = focused.value.slice(0, 7)
  const box = trigger.value!.getBoundingClientRect()
  position.value = { left: `${Math.max(12, Math.min(box.right - 258, window.innerWidth - 270))}px`, top: `${Math.max(12, Math.min(box.bottom + 6, window.innerHeight - 410))}px` }
  panel.value?.showPopover()
  await focusDate()
}

/** 月份导航不提交筛选值，跨年由标准日期运算处理。 */
function changeMonth(offset: number): void {
  const date = new Date(`${month.value}-01T00:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() + offset)
  month.value = date.toISOString().slice(0, 7)
  focused.value = `${month.value}-01`
}

/** 第一次点击选择起点，第二次点击组成有序闭区间，确认前只保留草稿。 */
function choose(value: string): void {
  if (!draftFrom.value || draftTo.value) { draftFrom.value = value; draftTo.value = '' }
  else { [draftFrom.value, draftTo.value] = [draftFrom.value, value].sort() as [string, string] }
  focused.value = value
}

/** 快捷范围包含今天，且允许确认前继续调整。 */
function shortcut(kind: number | 'month'): void {
  draftTo.value = today()
  draftFrom.value = kind === 'month' ? `${draftTo.value.slice(0, 7)}-01` : shift(draftTo.value, 1 - kind)
  month.value = draftTo.value.slice(0, 7)
  focused.value = draftTo.value
}

/** 日期网格使用单一 Tab 入口，方向键在日历内移动焦点。 */
async function keydown(event: KeyboardEvent, value: string): Promise<void> {
  const offsets: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }
  if (event.key in offsets) focused.value = shift(value, offsets[event.key]!)
  else if (event.key === 'PageUp' || event.key === 'PageDown') changeMonth(event.key === 'PageUp' ? -1 : 1)
  else return
  event.preventDefault()
  month.value = focused.value.slice(0, 7)
  await focusDate()
}

/** DOM 更新后聚焦当前日期，避免跨月时丢失键盘位置。 */
async function focusDate(): Promise<void> {
  await nextTick()
  panel.value?.querySelector<HTMLButtonElement>(`[data-date="${focused.value}"]`)?.focus()
}

/** 确认后由业务 Store 转换为北京时间边界；单日选择使用相同起止日。 */
function confirm(): void {
  emit('update:from', draftFrom.value)
  emit('update:to', draftTo.value || draftFrom.value)
  panel.value?.hidePopover()
  trigger.value?.focus()
}
</script>

<template>
  <div class="aima-date-range">
    <button
      ref="trigger"
      class="date-trigger"
      type="button"
      :aria-label="label"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="show"
    >
      <span>{{ from || '开始时间' }}</span><span>—</span><span>{{ to || '结束时间' }}</span><img
        src="../assets/calendar.svg"
        width="14"
        height="14"
        alt=""
      >
    </button>
    <div
      ref="panel"
      popover="auto"
      class="date-panel"
      :style="position"
      role="dialog"
      :aria-label="`选择${label}`"
      @toggle="open = $event.newState === 'open'"
    >
      <div class="month-nav">
        <button
          type="button"
          aria-label="上个月"
          @click="changeMonth(-1)"
        >
          ‹
        </button><strong aria-live="polite">{{ monthLabel }}</strong><button
          type="button"
          aria-label="下个月"
          @click="changeMonth(1)"
        >
          ›
        </button>
      </div>
      <div class="calendar-week">
        <span
          v-for="weekday in weekdays"
          :key="weekday"
        >{{ weekday }}</span>
      </div>
      <div class="calendar-days">
        <template
          v-for="(day, index) in days"
          :key="day ?? index"
        >
          <button
            v-if="day"
            type="button"
            :data-date="day"
            :aria-label="day"
            :aria-pressed="day === draftFrom || day === draftTo"
            :tabindex="day === focused ? 0 : -1"
            :class="{ endpoint: day === draftFrom || day === draftTo, between: draftFrom && draftTo && day > draftFrom && day < draftTo }"
            @click="choose(day)"
            @keydown="keydown($event, day)"
          >
            {{ Number(day.slice(-2)) }}
          </button><span v-else />
        </template>
      </div>
      <div class="date-shortcuts">
        <button
          type="button"
          @click="shortcut(1)"
        >
          今天
        </button><button
          type="button"
          @click="shortcut(7)"
        >
          近7天
        </button><button
          type="button"
          @click="shortcut(30)"
        >
          近30天
        </button><button
          type="button"
          @click="shortcut('month')"
        >
          本月
        </button>
      </div>
      <footer>
        <button
          class="clear-date"
          type="button"
          @click="draftFrom = ''; draftTo = ''"
        >
          清空
        </button><AimaButton
          size="small"
          @click="panel?.hidePopover()"
        >
          取消
        </AimaButton><AimaButton
          size="small"
          variant="primary"
          @click="confirm"
        >
          确定
        </AimaButton>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.aima-date-range { min-width: 0; }
.date-trigger { display: flex; width: 100%; height: 40px; min-width: 0; align-items: center; justify-content: center; gap: 5px; padding: 0 8px; border: 1px solid var(--aima-border-strong); border-radius: 6px; color: var(--aima-text-muted); background: #fff; font-size: 12px; cursor: pointer; white-space: nowrap; }
.date-panel { position: fixed; width: 258px; max-height: calc(100dvh - 24px); overflow-y: auto; margin: 0; padding: 16px 9px 12px; border: 1px solid var(--aima-border); border-radius: 8px; background: #fff; color: var(--aima-text); box-shadow: 0 6px 16px -2px rgb(0 0 0 / 10%); }
.month-nav { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }
.month-nav button { width: 24px; height: 24px; border: 0; color: var(--aima-text-muted); background: transparent; cursor: pointer; }
.calendar-week, .calendar-days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); text-align: center; }
.calendar-week { margin-bottom: 10px; color: var(--aima-text-disabled); font-size: 11px; line-height: 20px; }
.calendar-days { row-gap: 6px; }
.calendar-days button, .calendar-days > span { height: 34px; border: 0; border-radius: 6px; background: transparent; color: var(--aima-text); font-size: 13px; }
.calendar-days button { cursor: pointer; }
.calendar-days .endpoint { background: var(--aima-primary); color: #fff; }
.calendar-days .between { background: var(--aima-primary-soft); color: var(--aima-primary); }
.calendar-days button:focus-visible { outline: 2px solid var(--aima-primary); outline-offset: -2px; }
.date-shortcuts { display: flex; gap: 4px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--aima-border); }
.date-shortcuts button { flex: 1; height: 26px; border: 0; border-radius: 4px; background: var(--aima-color-bg-hover); color: var(--aima-text-muted); font-size: 11px; cursor: pointer; }
.date-panel footer { display: flex; gap: 8px; margin-top: 12px; justify-content: flex-end; }
.clear-date { margin-right: auto; padding: 0; border: 0; background: transparent; color: var(--aima-text-muted); font-size: 11px; cursor: pointer; }
</style>
