# Figma Prototype 状态与交互审计

静态截图正确，不代表 Prototype 正确。

这份 reference 专门检查只有在交互后才暴露的问题：旧变量回弹、重复文本、双图标、浮层漂移、错误 Flow、隐藏旧状态、滚动问题和演示伪成功。

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
Auto Layout / Constraints
Overflow / Scroll
Destination Node
```

只看普通 Metadata 不足以完成本层审计。

---

# 2. Flow Starting Point

正式基线应有明确入口。

多个 Flow 先判断：

- 是否代表不同独立任务；
- 是否存在历史/备份残留；
- 实现方会不会误选错误入口。

不要为了“只保留一个”机械删除真正独立流程。

---

# 3. Prototype Variable 默认值

默认值必须与当前正式 Data State 一致。

常见错误：

```text
画布已经是新数据
Prototype Variable 仍是旧数据
```

打开、切换或保存后就回弹。

重点搜索：

- 旧产品名；
- 旧数量；
- Stage/test/demo 脏文案；
- 已废弃字段；
- 旧选项；
- 旧状态枚举。

---

# 4. Reaction 中的隐藏赋值

必须检查 `SET_VARIABLE` 和 `CHANGE_TO`。

典型问题：

```text
Success 组件自带图标
+
Reaction 把图标字符写入 Message
→ 双图标
```

或者：

```text
点击重置
→ Prototype 把结果数改成与正式样例不一致的旧值
```

规则：

> 任何会改变 UI 的 Action 都必须和当前正式状态一起审计。

---

# 5. 重复文字与重复组件

典型结构：

```text
Feedback Instance
└─ Message
+
外部动态 Text
```

触发时会文字重影。

修复原则：

```text
只保留一个状态源
```

动态值优先绑定公共组件 Property，而不是在组件外覆盖。

---

# 6. Toast / Popover / Dropdown / Tooltip

相同模式应有统一定位和安全区。

检查：

- 是否挡住导航、头像、主按钮；
- 是否被父级裁切；
- 是否超出 Viewport / Safe Area；
- 不同页面位置是否漂移；
- z-order 是否正确；
- Auto Layout 父级中的浮层是否需要 `ABSOLUTE`。

不能只写 x/y 后假设不会被重新布局。

---

# 7. Dropdown / Menu

至少检查：

- trigger 状态；
- menu visible；
- 当前选中值；
- option Reaction；
- 选中后是否关闭；
- option 是否真实有效；
- 长文本是否截断；
- menu 是否被 Scroll Container 裁切。

用户文案与机器值不同的，在 Annotation/规格里记录映射。

---

# 8. Modal / Drawer / Sheet

检查：

```text
Header
Body
Footer
滚动容器
关闭路径
返回路径
Overlay 层级
```

避免多层滚动。

移动端还应检查 Safe Area、键盘顶起和底部操作区；桌面端检查窗口高度变化。

---

# 9. Prototype 不伪造真实系统成功

以下行为可能依赖真实系统：

```text
保存持久化数据
远程请求
支付/提交
后台任务完成
文件上传成功
设备操作成功
```

Prototype 可以展示代表性成功状态，但不能把演示跳转当作系统一定成功的证据。

标注：

```text
Representative State
≠
真实执行结果
```

---

# 10. Prototype Machine Audit

完成前建议扫描：

```text
旧产品名
旧测试字符串
手写 ✓ / × / ! 等重复图标字符
失效 destination
重复同坐标提示
旧组件/旧视觉块
隐藏旧状态
```

零命中只证明这些已知问题没有命中，不自动证明整个 Prototype 完美。

---

# 11. 修复后验证

至少：

1. 重新读取受影响 Variable / Reaction；
2. 临时切到目标状态；
3. Fresh Screenshot；
4. 恢复默认状态；
5. 再扫描旧值；
6. 修改公共组件时抽查其它消费者；
7. Design-to-Code 项目重新读取 Design Context（适用时）。

不能因为工具写入返回成功就宣称 Prototype 已修好。
