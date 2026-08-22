# TikHub 真实请求响应与接口选型台账：兼容导航

这个文件用于兼容早期文档、Change 和代码导航中已经使用的旧路径。

当前正式、完整且持续维护的接口选型/真实验证台账是：

[`TikHub接口选型与真实验证台账.md`](TikHub接口选型与真实验证台账.md)

它用于回答：

- 当前五个平台主接口到底选了哪一条；
- 哪些 App/Web/V1/V2/V3 组合做过真实 Probe；
- 哪些只是备用接口；
- 哪些 Fixture 是当前主链证据；
- 某次验证的价格/限制/失败结论是什么。

原 Blueprint 12 的完整历史验证台账仍保存在：

[`../blueprint/12-TikHub真实请求响应与接口选型台账.md`](../blueprint/12-TikHub真实请求响应与接口选型台账.md)

判断当前生产接口时，以当前 `adapters/providers/tikhub/operations/`、Capability、Fixture、测试和正式新台账为准；本兼容文件不维护第二份接口结论。
