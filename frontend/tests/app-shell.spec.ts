import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppShell from '../src/app/layouts/AppShell.vue'

function renderShell() {
  return mount(AppShell, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to"><slot /></a>',
        },
      },
    },
  })
}

describe('AppShell 内网 V1 导航', () => {
  it('首页和三个首版业务页面都是可导航入口', () => {
    const wrapper = renderShell()

    expect(wrapper.find('a[href="/"]').text()).toContain('首页')
    expect(wrapper.find('a[href="/voice-plaza"]').text()).toContain('声音广场')
    expect(wrapper.find('a[href="/collection-runtime"]').text()).toContain('采集运行中心')
    expect(wrapper.find('a[href="/collection-strategy"]').text()).toContain('采集策略')
  })

  it('不把尚未实现的未来能力显示成无效菜单项', () => {
    const text = renderShell().text()

    for (const label of ['智能洞察', '销售漏斗', '热点捕捉', '管理员页面', '帮助与反馈']) {
      expect(text).not.toContain(label)
    }
  })
})
