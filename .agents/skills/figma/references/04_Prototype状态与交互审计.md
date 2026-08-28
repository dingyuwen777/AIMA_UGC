# Figma Prototype 状态与交互审计

静态截图正确，不代表 Prototype 正确。

这份 reference 专门检查那些只有“点击以后”才会暴露的问题：旧变量回弹、重复文本、Toast 漂移、错误 Flow、隐藏旧状态和演示伪成功。

---

# 1. 必查对象

至少检查：

```text
Flow Starting Point
Reaction
Prototype Variable
Variable 默认值
SET_VARIABLE Action
NODE / OVERLAY / CHANGE_TO
Open / Close
Hidden Layer
Absolute Position
Auto Layout
Overflow / Scroll
Destination Node
```

只看普通 Metadata 不足以完成本层审计。

---

# 2. Flow Starting Point

正式开发基线通常应有一个明确起点。

发现多个 Flow 时先判断：

- 是否一个是历史参考；
- 是否多个 Flow 分别代表独立用户任务；
- 是否只是历史残留。

如果同一正式页面有多个互相竞争的 starting point，应形成 Finding。

不要为了“整洁”机械删除真正独立流程。

---

# 3. Prototype Variable 默认值

变量默认值必须与当前正式 Data State 一致。

常见错误：

```text
画布显示：词包 28词
变量默认：3词
```

打开/切换状态后就会回到旧数据。

审查时搜索：

- 旧名称；
- 旧数量；
- Stage/test 文案；
- 历史 Provider 名；
- 旧状态枚举；
- 已废弃字段。

---

# 4. Reaction 中的隐藏赋值

必须检查 `SET_VARIABLE`，因为画布文字已经改掉时，Reaction 仍可能保留旧值。

例如：

```text
保存成功后
→ 设置 notice.text = "✓ 保存成功"
```

如果 Success 组件本身已有图标，就会出现双对号。

又例如：

```text
点击查询
→ result_count = 25
```

而正式示例数据已经是 24 条，会造成演示自相矛盾。

规则：

> 任何会更新 UI 的 Prototype Action，都要和当前正式视觉状态一起审计。

---

# 5. 重复文字与重复组件

典型结构错误：

```text
Feedback Instance
└─ Message

+
外部动态 Text
```

两层位置相同，触发时出现重影。

或者：

```text
Success Icon = ✓
Message = "✓ 已更新"
```

出现双图标。

修复原则：

```text
只保留一个状态源
```

优先把动态值绑定进公共组件 Property，而不是在组件外再覆盖。

---

# 6. Toast / Popover / Dropdown 位置

相同模式在不同页面应遵循同一定位规则。

例如顶部居中 Toast：

```text
固定宽度
x = (viewport - toastWidth) / 2
y = topOffset
```

如果父级是 Auto Layout，必须检查浮层是否脱离布局流。

常见错误：

```text
设置 x/y 成功
→ Auto Layout 下一次重新布局
→ 节点又被排到别处
```

根因不是坐标值，而是 `layoutPositioning`。

---

# 7. Dropdown / Menu

下拉菜单至少检查：

- trigger 状态；
- menu visible 变量；
- 当前选中值；
- 每个 option 的 Reaction；
- 选中后是否关闭；
- option 是否真实对应后端能力；
- menu 是否被父级 `clipsContent` 裁切。

如果用户看到自然语言选项，但后端需要机器值，应在 Annotation 记录映射。

例如：

```text
每6小时
→ schedule_expr = 0 */6 * * *
```

---

# 8. Modal / Drawer

检查：

```text
Header 固定？
Body 是否唯一滚动容器？
Footer 是否固定？
Top-level 是否又开启第二层滚动？
关闭按钮 / Backdrop 是否回到正确页面？
```

避免：

```text
整个 Drawer 滚动
+
Body 也滚动
```

造成双层滚动。

---

# 9. Prototype 不伪造服务器成功

依赖真实服务器的行为，例如：

- 创建任务；
- 保存数据库；
- Provider 请求；
- Worker 执行；
- 调度任务真正开始；

Prototype 可以展示“成功后页面应该长什么样”，但不应让演示跳转本身成为“真实系统一定成功”的证据。

正确标注：

```text
代表性成功状态
实际结果由 API / Worker / Runtime 决定
```

---

# 10. Prototype Machine Audit

完成前建议做关键词和结构扫描：

```text
旧产品名
旧测试字符串
旧 Provider 名
手写 ✓ / × / ! / ⓘ
失效 destinationId
重复同坐标提示
旧 Component / Visual Block
```

零命中只能证明扫描集合没有这些已知问题，不能自动证明整个 Prototype 完美。

---

# 11. 修复后验证

至少：

1. 重新读取受影响 Reaction / Variable；
2. 临时切到目标状态；
3. Fresh Screenshot；
4. 恢复默认变量状态；
5. 再扫描一次旧值；
6. 如目标是 Design-to-Code，再重新读取 Design Context。

不能因为脚本写入成功就宣称 Prototype 已修好。
