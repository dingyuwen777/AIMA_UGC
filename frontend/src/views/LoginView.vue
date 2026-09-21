<script setup lang="ts">
import { computed, onMounted, onServerPrefetch, ref } from 'vue'
import { useRoute } from 'vue-router'

import { useIdentityStore } from '../features/identity/store'

const route = useRoute()
const identity = useIdentityStore()

/** 可登录企业的列表端点。**单企业部署时它不存在（404）**，所以下面必须容忍失败。 */
const CONNECTORS_ENDPOINT = '/api/v1/auth/connectors'

/** 一个可登录的飞书企业（只取展示与路由所需的两个字段，与后端契约一致）。 */
interface LoginConnector {
  code: string
  display_name: string
}

const connectors = ref<LoginConnector[]>([])

/**
 * 把接口返回的一项收窄成 `LoginConnector`。
 *
 * 为什么要在前端做这层检查：这是登录页的**唯一**数据依赖，它一旦抛错就会白屏。
 * 这里宁可"丢掉一条形状不对的数据"，也不让整页渲染失败。
 */
function toConnector(value: unknown): LoginConnector | null {
  if (typeof value !== 'object' || value === null) return null
  const candidate = value as Record<string, unknown>
  const code = candidate.code
  const displayName = candidate.display_name
  if (typeof code !== 'string' || code === '') return null
  if (typeof displayName !== 'string' || displayName === '') return null
  return { code, display_name: displayName }
}

/**
 * 读取可登录企业列表。
 *
 * ⚠️ 这个请求**刻意不是**"必须成功"的：
 * · 单企业部署时后端根本不注册该端点（404）；
 * · 它在登录页、未认证状态下调用，网络/服务异常都可能发生。
 * 因此**任何失败都只把列表留空**，页面随后走"单个飞书登录按钮"的降级分支 ——
 * 绝不能让一个可选接口把整个登录入口拖down。
 */
async function loadConnectors(): Promise<void> {
  try {
    const response = await fetch(CONNECTORS_ENDPOINT, {
      headers: { Accept: 'application/json' },
    })
    // 404（单企业）/ 5xx 等都按"拿不到列表"处理，不区分——对用户而言结果一样。
    if (!response.ok) return
    const payload: unknown = await response.json()
    const items = (payload as { items?: unknown }).items
    if (!Array.isArray(items)) return
    connectors.value = items
      .map(toConnector)
      .filter((item): item is LoginConnector => item !== null)
  } catch {
    // 静默降级：登录页不因企业列表拿不到而报错。
  }
}

/**
 * 两个环境各取所需：SSR 时等 `onServerPrefetch`（这样首屏 HTML 就带正确的企业信息），
 * 浏览器端走 `onMounted`。二者互斥，不会重复请求。
 */
onServerPrefetch(loadConnectors)
onMounted(() => {
  void loadConnectors()
})

/**
 * URL 上的企业标识参数名是**短名 `c`**（飞书后台的「网页应用主页」要手填这个地址，
 * 越短越不容易配错）；传给后端时参数名是 **`connector`**（后端契约如此）。
 * 两者的对应关系就在这里，不要在模板里散落 `route.query.c`。
 */
const requestedConnector = computed(() =>
  typeof route.query.c === 'string' ? route.query.c.trim() : '',
)

/** URL 指定的企业在列表里对应的那条记录；拿不到就是 `null`（走降级分支）。 */
const selectedConnector = computed(
  () => connectors.value.find((item) => item.code === requestedConnector.value) ?? null,
)

/**
 * 多企业可选项：**只有 ≥2 家时才用它渲染列表**。
 *
 * 为什么把"1 家不算列表"写在这里而不是模板里：单企业是线上现状，必须保持
 * 改造前的单个「飞书登录」按钮。把它收敛成一个 computed，模板只剩"用不用它"两分支。
 *
 * ⚠️ 模板里刻意**不写 HTML 注释**：Vue 会把模板注释原样渲染进 HTML，
 * 那样单企业形态的输出就会多出一段注释，破坏"与改造前逐字一致"的兼容性红线。
 * 列表顺序沿用后端返回顺序（= 配置顺序），前端不重排，保证每次刷新按钮次序一致。
 */
const connectorList = computed(() => (connectors.value.length >= 2 ? connectors.value : []))

/**
 * 是否展示企业选择列表。两个条件缺一不可：
 * · 列表里有 **≥2 家**（只有 1 家时保持改造前的单按钮形态 —— 兼容性红线）；
 * · **URL 没带 `?c=`** —— 带了就是"已从某家企业的入口进来"，
 *   此时要么显示企业名、要么降级成通用文案，**不该再让用户选一次**。
 */
const showConnectorList = computed(
  () => requestedConnector.value === '' && connectorList.value.length >= 2,
)

/**
 * 发起飞书登录。
 *
 * ⚠️ 必须用整页跳转（`window.location.assign`）而不是 `fetch`：
 * 后端要 302 到飞书授权页并由浏览器完成跳转，`fetch` 不会跟随跨站跳转，
 * Cookie 也不会按预期走。同时把当前地址作为 `return_to` 带上（后端会再做白名单校验）。
 *
 * `connectorCode` 为空时**不传 `connector` 参数** —— 这正是改造前单企业部署的请求形态
 * （`/api/v1/auth/feishu/login`），必须逐字保持。
 */
function loginHrefFor(connectorCode = ''): string {
  const params = new URLSearchParams()
  const returnTo = typeof route.query.return_to === 'string' ? route.query.return_to : undefined
  if (returnTo) params.set('return_to', returnTo)
  if (connectorCode) params.set('connector', connectorCode)
  const query = params.toString()
  return `/api/v1/auth/feishu/login${query ? `?${query}` : ''}`
}

/**
 * 主按钮地址：优先用 URL 上的 `?c=`（即使列表还没取到也要带上，
 * 这样"自动路由"不依赖那个可选接口是否可用）。
 */
const loginHref = computed(() => loginHrefFor(requestedConnector.value))
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1>爱玛用户声音</h1>
      <p class="subtitle">
        智能监测与洞察平台
      </p>

      <p
        v-if="selectedConnector"
        class="hint connector-notice"
      >
        你正在从【{{ selectedConnector.display_name }}】登录
      </p>
      <p
        v-else-if="showConnectorList"
        class="hint"
      >
        请选择您的企业
      </p>
      <p
        v-else
        class="hint"
      >
        请使用企业飞书账号登录。
      </p>

      <template v-if="showConnectorList">
        <a
          v-for="connector in connectorList"
          :key="connector.code"
          class="login-action"
          :href="loginHrefFor(connector.code)"
        >{{ connector.display_name }}</a>
      </template>
      <a
        v-else
        class="login-action"
        :href="loginHref"
      >飞书登录</a>

      <p
        v-if="identity.forbidden"
        class="notice"
        role="alert"
      >
        当前账号没有访问权限，请联系统一管理员。
      </p>
    </div>
  </div>
</template>

<style scoped>
/*
 * 登录页。数据依赖只有一个**可选**接口（可登录企业列表），拿不到就退回单按钮形态。
 * 视觉目标：让中间的卡片“浮”在页面上，而不是贴在页面上。
 * 全部层次只用 CSS 实现（渐变 + 阴影），不引入任何图片或新依赖。
 */
.login-page {
  display: grid;
  min-height: 100vh;
  padding: var(--aima-spacing-2xl);
  place-items: center;
  background-color: var(--aima-color-bg-page);
  /*
   * 极淡的品牌色径向光晕，中心略高于卡片：给纯色底加一点明暗层次，
   * 卡片压在上面时立体感更明显。拆成 background-image 单独声明，
   * 这样即使引擎不支持 color-mix，也只是少一层光晕，底色仍然正确。
   */
  background-image: radial-gradient(
    70% 55% at 50% 38%,
    color-mix(in srgb, var(--aima-color-primary) 5%, transparent) 0%,
    transparent 70%
  );
}
.login-card {
  display: grid;
  width: 320px;
  max-width: 100%;
  gap: var(--aima-spacing-md);
  padding: var(--aima-spacing-3xl);
  /* 兜底边框：不支持 color-mix 时保持原样，下面再把它调淡。 */
  border: var(--aima-border-width-default) solid var(--aima-color-border-default);
  border-color: color-mix(in srgb, var(--aima-color-border-default) 45%, transparent);
  border-radius: 16px;
  background: var(--aima-color-bg-white);
  text-align: center;
  /* 兜底阴影：不支持 color-mix 时至少保留一层浅投影，避免卡片完全变平。 */
  box-shadow: 0 1px 2px var(--aima-color-border-strong);
  /*
   * 三层阴影（近距离锐利 + 中距离扩散 + 远距离大模糊）：
   * 近层勾出卡片边缘，中层给出厚度，远层用较大模糊与负扩散表现“离地高度”。
   * 阴影色统一由 --aima-color-text-primary 稀释而来，不在组件里硬编码颜色。
   */
  box-shadow:
    0 1px 2px color-mix(in srgb, var(--aima-color-text-primary) 10%, transparent),
    0 6px 16px color-mix(in srgb, var(--aima-color-text-primary) 8%, transparent),
    0 20px 40px -12px color-mix(in srgb, var(--aima-color-text-primary) 14%, transparent);
}
.login-card h1 {
  margin: 0;
  color: var(--aima-color-text-primary);
  font-size: 20px;
  /* 字号保持 20px 不变（企业内部系统，保持克制），层级靠字重与颜色拉开。 */
  font-weight: 600;
  line-height: var(--aima-line-height-heading);
}
.subtitle,
.hint {
  margin: 0;
  line-height: var(--aima-line-height-body);
}
.subtitle {
  color: var(--aima-color-text-secondary);
  font-size: var(--aima-font-size-body-small);
}
.hint {
  /*
   * 刻意不用 --aima-color-text-tertiary：该令牌是浅灰蓝，在白底上对比度只有约 2.1:1，
   * 低于 WCAG AA 要求的 4.5:1。提示语属于用户要读的说明文字，层级只靠字号拉开，
   * 不靠降低对比度，避免“为了好看”牺牲可读性。
   */
  color: var(--aima-color-text-secondary);
  font-size: var(--aima-font-size-caption);
}
/*
 * 「你正在从【XX 企业】登录」：这句话是防"走错门"的提示——用户从某家企业的
 * 飞书工作台点进来，得让他确认自己没进错企业的登录页。因此它**不是**普通灰色提示语，
 * 用品牌主色加中等字重把它抬成"当前状态"，与下面的按钮形成一组。
 * 只借令牌取色，不硬编码颜色，换主题时自动跟随。
 */
.connector-notice {
  color: var(--aima-color-primary);
  font-weight: 600;
}
.login-action {
  display: grid;
  min-height: var(--aima-control-height-md);
  margin-top: var(--aima-spacing-sm);
  padding: var(--aima-spacing-sm) var(--aima-spacing-lg);
  place-items: center;
  border-radius: var(--aima-radius-lg);
  background: var(--aima-color-primary);
  box-shadow: 0 1px 2px var(--aima-color-border-strong);
  /* 品牌色投影，强化“可点击”的实体感；同样不硬编码颜色。 */
  box-shadow:
    0 1px 2px color-mix(in srgb, var(--aima-color-primary) 18%, transparent),
    0 6px 14px -6px color-mix(in srgb, var(--aima-color-primary) 45%, transparent);
  color: var(--aima-color-text-inverse);
  text-decoration: none;
  font-size: var(--aima-font-size-control);
  line-height: var(--aima-line-height-compact);
  transition:
    background-color 160ms ease,
    box-shadow 160ms ease,
    transform 120ms ease;
}
.login-action:hover {
  background: var(--aima-color-primary-hover);
  box-shadow:
    0 1px 2px color-mix(in srgb, var(--aima-color-primary) 20%, transparent),
    0 8px 18px -6px color-mix(in srgb, var(--aima-color-primary) 55%, transparent);
}
.login-action:active {
  background: var(--aima-color-primary-active);
  box-shadow: 0 1px 2px color-mix(in srgb, var(--aima-color-primary) 28%, transparent);
  transform: translateY(1px);
}
/*
 * 键盘可达性：保留可见焦点环（outline + 品牌色柔光环），不依赖鼠标 hover 才能看见状态。
 */
.login-action:focus-visible {
  outline: var(--aima-border-width-focus) solid var(--aima-color-primary);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--aima-color-focus-ring);
}
.notice {
  margin: 0;
  padding: var(--aima-spacing-sm) var(--aima-spacing-md);
  border: var(--aima-border-width-default) solid var(--aima-color-error);
  border-radius: var(--aima-radius-lg);
  background: var(--aima-color-error-bg);
  color: var(--aima-color-error);
  font-size: var(--aima-font-size-caption);
  font-weight: 600;
  line-height: var(--aima-line-height-compact);
}
</style>
