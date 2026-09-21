import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import AppShell from '../src/app/layouts/AppShell.vue'
import { resolveAvatarUrl } from '../src/features/identity/avatar'
import { useIdentityStore, type PrincipalOutcome } from '../src/features/identity/store'

type IdentityStore = ReturnType<typeof useIdentityStore>

type Principal = NonNullable<IdentityStore['principal']>

/** 一份完整的正常身份，测试只覆盖需要区分的字段。 */
function principal(overrides: Partial<Principal> = {}): Principal {
  return {
    principal_id: 'p-1',
    display_name: '普通用户',
    role: 'user',
    source: 'feishu',
    is_administrator: false,
    ...overrides,
  }
}

/**
 * 用真实 Pinia 身份状态渲染 AppShell。
 *
 * 这里沿用既有 `app-shell.spec.ts` 的 SSR 渲染方式（项目未安装 jsdom/happy-dom，
 * 不能做 DOM 挂载，也不能真实触发 `<img>` 的 error 事件），因此：
 * · "渲染出什么" 由 SSR HTML 断言；
 * · "加载失败该显示什么" 由导出的纯函数 `resolveAvatarUrl` 断言。
 */
async function renderShell(configure: (store: IdentityStore) => void = () => {}): Promise<string> {
  const routerLink = defineComponent({
    props: { to: { type: String, required: true } },
    setup(props, { slots }) {
      return () => h('a', { href: props.to }, slots.default?.())
    },
  })
  const app = createSSRApp({ render: () => h(AppShell) })
  const pinia = createPinia()
  app.use(pinia)
  configure(useIdentityStore(pinia))
  app.component('RouterLink', routerLink)
  return renderToString(app)
}

/**
 * SSR 会在 `<template v-else>` 这类片段边界插入 `<!--[-->` 注释，
 * 断言"页面上看得见的文字"前先统一去掉，避免断言绑死在实现细节上。
 */
function plain(html: string): string {
  return html.replace(/<!--[\s\S]*?-->/g, '')
}

/**
 * 只取身份**文字区**（`.principal`）。
 * 悬浮提示挂在它的父层 `.account-identity` 的 `title` 属性上，属于"藏起来的信息"，
 * 不能被当成页面上可见的状态文案 —— 否则"正常时不显示异常提示"这类断言会被提示词本身误伤。
 */
function identityBlock(html: string): string {
  const start = html.indexOf('class="principal"')
  const end = html.indexOf('class="account-actions"')
  return start === -1 ? '' : html.slice(start, end === -1 ? undefined : end)
}

/** 让身份处于指定异常态：没有 principal，只有 store 里已有的 outcome 分类字段。 */
function failed(outcome: PrincipalOutcome, error: string | null = '服务暂不可用') {
  return (store: IdentityStore): void => {
    store.principal = null
    store.outcome = outcome
    store.principalError = error
  }
}

describe('头像：优先图片，拿不到就回退姓名首字', () => {
  it('有 avatar_url 时渲染 <img>，且不带文字回退', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '本地管理员', avatar_url: 'https://example.com/a.png' })
    })

    expect(html).toContain('class="avatar-image"')
    expect(html).toContain('src="https://example.com/a.png"')
  })

  it('没有 avatar_url 时渲染姓名首字（不出现空头像）', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三' })
    })

    expect(html).not.toContain('avatar-image')
    expect(plain(html)).toContain('>张</span>')
  })

  it('avatar_url 为 null 时同样回退首字', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '李四', avatar_url: null })
    })

    expect(html).not.toContain('avatar-image')
    expect(plain(html)).toContain('>李</span>')
  })

  it('图片加载失败后判定为空，界面回退首字而不是空白', () => {
    // ⚠️ 这是 DoD「加载失败 → 回退首字」的可执行证据：模板里 `<img>` 的 error 事件把
    // avatarFailed 置为 true，而 avatarUrl 完全由这个纯函数决定 —— 失败即返回 null，
    // 于是 `v-if="avatarUrl"` 为假、回退分支渲染首字。
    expect(resolveAvatarUrl('https://example.com/broken.png', true)).toBeNull()
    // 反向自检：同一个地址在"没失败"时必须真的被用来渲染图片，否则上面的断言可能只是恒为 null。
    expect(resolveAvatarUrl('https://example.com/ok.png', false)).toBe('https://example.com/ok.png')
  })

  it('空串与纯空格按"没有头像"处理，避免 src="" 的碎图', () => {
    expect(resolveAvatarUrl('', false)).toBeNull()
    expect(resolveAvatarUrl('   ', false)).toBeNull()
    expect(resolveAvatarUrl(undefined, false)).toBeNull()
    expect(resolveAvatarUrl(null, false)).toBeNull()
  })

  it('地址两端空白会被裁掉，避免带空格的 URL 请求失败', () => {
    expect(resolveAvatarUrl('  https://example.com/a.png  ', false)).toBe('https://example.com/a.png')
  })
})

describe('角色视觉标识：管理员与普通用户一眼可辨', () => {
  it('管理员渲染橙色管理员徽标', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '本地管理员', role: 'administrator', is_administrator: true })
    })

    expect(html).toContain('role-badge--administrator')
    expect(html).toContain('管理员')
  })

  it('普通用户渲染灰色普通用户徽标，且不带管理员徽标', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三', role: 'user' })
    })

    expect(html).toContain('role-badge--user')
    expect(html).toContain('普通用户')
    expect(html).not.toContain('role-badge--administrator')
  })

  it('两种角色的徽标样式类互不相同', async () => {
    const administrator = await renderShell((store) => {
      store.principal = principal({ role: 'administrator', is_administrator: true })
    })
    const ordinary = await renderShell((store) => {
      store.principal = principal({ role: 'user' })
    })

    expect(administrator).not.toContain('role-badge--user')
    expect(ordinary).not.toContain('role-badge--administrator')
  })
})

describe('权限来源提示：告诉用户权限来自飞书用户组', () => {
  it('飞书身份悬浮提示指向飞书用户组', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ source: 'feishu' })
    })

    expect(html).toContain('title="权限来自飞书用户组；如需调整，请联系管理员在飞书后台修改用户组成员"')
  })

  it('本地开发身份不谎称权限来自飞书用户组', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ source: 'development' })
    })

    expect(html).toContain('权限不来自飞书用户组')
  })
})

describe('异常态按 outcome 三态区分（复用 store 既有字段，不新增状态）', () => {
  it('401 未登录：显示未登录并提供去登录入口', async () => {
    const html = await renderShell(failed('unauthenticated'))

    expect(html).toContain('未登录')
    expect(html).toContain('去登录')
    expect(html).toContain('href="/login"')
  })

  it('403 无权限：提示联系管理员，且**不**给去登录入口（避免登录死循环）', async () => {
    const html = await renderShell(failed('forbidden'))

    expect(html).toContain('无权限')
    expect(html).toContain('联系管理员')
    expect(html).not.toContain('href="/login"')
    expect(html).not.toContain('去登录')
  })

  it('服务异常：提示服务异常并提供重试', async () => {
    const html = await renderShell(failed('error'))

    expect(html).toContain('服务异常')
    expect(html).toContain('重试')
    expect(html).not.toContain('href="/login"')
  })

  it('三种异常态互相不串味', async () => {
    const unauthenticated = identityBlock(await renderShell(failed('unauthenticated')))
    const forbidden = identityBlock(await renderShell(failed('forbidden')))
    const error = identityBlock(await renderShell(failed('error')))

    expect(unauthenticated).not.toContain('联系管理员')
    expect(unauthenticated).not.toContain('服务异常')
    expect(forbidden).not.toContain('未登录')
    expect(forbidden).not.toContain('服务异常')
    expect(error).not.toContain('未登录')
    expect(error).not.toContain('联系管理员')
  })

  it('身份仍在加载时不冒充未登录', async () => {
    const html = await renderShell() // 默认 outcome 为 ok、没有 principal

    expect(html).toContain('身份加载中')
    expect(html).not.toContain('去登录')
  })

  it('身份正常时不显示任何异常态提示', async () => {
    // 只看身份文字区：悬浮提示里本来就会说明"权限来自飞书用户组"，那是藏起来的信息，不是状态文案。
    const block = identityBlock(await renderShell((store) => {
      store.principal = principal({ display_name: '张三' })
    }))

    expect(block).not.toContain('未登录')
    expect(block).not.toContain('联系管理员')
    expect(block).not.toContain('服务异常')
    expect(block).not.toContain('身份加载中')
  })
})

describe('部门行：有就显示，没有就整行不出现', () => {
  it('有部门名时渲染「部门：<名称>」', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三', department_name: 'Project_Aima_CN01P000637' })
    })

    expect(html).toContain('class="principal-department"')
    expect(plain(html)).toContain('部门：Project_Aima_CN01P000637')
  })

  it('department_name 为 null 时**不渲染**部门元素（不能出现「部门：null」）', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三', department_name: null })
    })

    // 断言"元素不存在"，而不是断言"文字不等于 null" —— 后者无法排除「部门：null」这种写法。
    expect(html).not.toContain('principal-department')
    expect(plain(html)).not.toContain('部门')
  })

  it('department_name 为空串或纯空格时同样不渲染部门元素', async () => {
    for (const empty of ['', '   ']) {
      const html = await renderShell((store) => {
        store.principal = principal({ display_name: '张三', department_name: empty })
      })

      expect(html).not.toContain('principal-department')
      expect(plain(html)).not.toContain('部门')
    }
  })

  it('字段整体缺失（未登录时向飞书取部门失败）时不渲染部门元素', async () => {
    // 后端该字段可选：`principal()` 默认不传 department_name，等价于真实响应里没有这个键。
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三' })
    })

    expect(html).not.toContain('principal-department')
  })

  it('身份仍在异步加载（principal 为 null）时不渲染部门元素', async () => {
    // 默认 store 就是"还没拿到 Principal"，此时不能凭空值渲染出一个空部门行。
    const html = await renderShell()

    expect(html).not.toContain('principal-department')
    expect(plain(html)).not.toContain('部门')
  })

  it('异常态（未登录 / 无权限 / 服务异常）下不渲染部门元素', async () => {
    for (const outcome of ['unauthenticated', 'forbidden', 'error'] as PrincipalOutcome[]) {
      const html = await renderShell(failed(outcome))

      expect(html).not.toContain('principal-department')
    }
  })

  it('加上部门行后姓名仍然完整渲染，没有被挤掉', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三', department_name: 'Project_Aima_CN01P000637' })
    })

    // 上一轮的坑：180px 侧栏里横向塞太多东西，短姓名被截成「N…」。
    // 部门行是**纵向追加**的第三行，姓名的元素与文字都必须原样保留。
    expect(html).toContain('class="principal-name"')
    expect(plain(html)).toContain('张三')
    // 角色徽标也还在，说明这条追加没有顶掉原有行。
    expect(html).toContain('role-badge--user')
  })

  it('部门行与姓名同处身份文字区，且排在姓名之后', async () => {
    const block = identityBlock(await renderShell((store) => {
      store.principal = principal({ display_name: '张三', department_name: 'Project_Aima_CN01P000637' })
    }))

    expect(block).toContain('张三')
    expect(block).toContain('部门：Project_Aima_CN01P000637')
    expect(block.indexOf('张三')).toBeLessThan(block.indexOf('部门：'))
  })

  it('超长部门名可由 title 悬浮查看完整值（省略号截断的兜底）', async () => {
    const longName = 'Project_Aima_CN01P000637_Extra_Long_Department_Name'
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三', department_name: longName })
    })

    // 侧栏只有 180px，长部门名必然靠 CSS 省略号收尾；但完整值不能就此丢失。
    expect(html).toContain(`title="部门：${longName}"`)
  })
})

describe('账户区布局与既有能力不被破坏', () => {
  it('姓名与角色处在独立的两行，操作（退出 / 消息）另起一行，不与姓名抢宽度', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三' })
    })

    // 旧版把 32px 头像 + 退出 + 铃铛挤在同一行，姓名只剩约 20px 宽 → 短名字也被截成「N…」。
    // 现在姓名所在行只有头像 + 姓名 + 角色，操作下沉到 .account-actions。
    expect(html).toContain('class="account-identity"')
    expect(html).toContain('class="account-actions"')
    const identityRow = html.split('class="account-actions"')[0] ?? ''
    const actionsRow = html.split('class="account-actions"')[1] ?? ''
    expect(identityRow).toContain('张三')
    expect(identityRow).not.toContain('退出')
    expect(actionsRow).toContain('退出')
  })

  it('登出入口与站内通知仍在侧栏底部', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ display_name: '张三' })
    })
    const sidebar = html.split('</aside>')[0] ?? ''

    expect(sidebar).toContain('退出')
    expect(sidebar).toContain('title="退出登录"')
    expect(sidebar).toContain('aria-label="站内通知"')
  })

  it('管理员仍保留独立配置入口', async () => {
    const html = await renderShell((store) => {
      store.principal = principal({ role: 'administrator', is_administrator: true })
    })

    expect(html).toContain('href="/admin/configuration"')
  })
})
