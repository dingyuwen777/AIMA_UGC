# TikHub 小红书测试 Fixture

[`tests/fixtures/providers/tikhub/xiaohongshu/search_notes_page1.sanitized.json`](search_notes_page1.sanitized.json) 来源于项目 Owner 于 2026-08-05 使用 TikHub Xiaohongshu App V2 `search_notes`、关键词“爱玛”、`page=1`、`sort_type=time_descending`、`note_type=不限`、`time_filter=一天内`、`source=explore_feed` 取得的真实成功响应。

该 Fixture 只保留验证 Provider Operation、分页和 Mapper 所需的结构与字段类型；提交前已替换真实笔记 ID、账号 ID、昵称、标题和正文，并删除 `xsec_token`、缓存签名 URL、CDN 签名 URL、调试令牌和其他不参与当前 Contract 的供应商私有字段。它用于证明已观察到的 App V2 搜索响应结构，不代表详情/评论接口的真实兼容验收。

真实付费 Probe 默认不进入 CI；API Key 不允许写入本目录、源码、日志、Raw Fixture 或 Git 历史。

2026-08-14 经项目 Owner 明确授权，使用关键词“爱玛”对同一 `search_notes` endpoint 执行了两次最小只读
兼容 Probe；两次均返回 HTTP 200，但 `items=[]`。该证据只确认当次顶层包装、`data`、搜索会话/下一页字段
和空页停止结构，没有保存真实响应，也不替换本目录的脱敏非空 Fixture。详情和评论端点未执行真实 Probe。

2026-10-09 的同一视频笔记详情验证另保存为 [视频详情](video_detail_20261009.sanitized.json) 与 [图文端点返回的视频封面](video_cover_detail_20261009.sanitized.json)。所有笔记/账号 ID、标题、正文、URL 路径和签名均替换为 synthetic 或脱敏占位值；只保留真实包装、字段、枚举、数值单位及流层次。视频详情证明 `video_info_v2.media.stream.h264` 中的 MP4/AAC 流及毫秒时长、所选流尺寸；图文端点同 ID 只返回封面，不证明播放 URL 缺失应清空旧值。

当轮另由 Parent 在本机出口验证主、备用视频 CDN 的同路径 HTTPS、TLS 主机名、公网 DNS/IP 固定和 Range 206/416；Fixture URL 是 synthetic，不能用作真实播放验收，也不能据此宣称部署出口已验证。真实费用审计由当轮 Requirement/Change Evidence 追溯；永久回归不发送 Provider 请求。

[旧 Canonical wire](canonical_90013af0.sanitized.json) 使用固定 `90013af0a07c32a17509adb4deb7509ad97927c9` 的 Mapper 对本目录脱敏 Raw 与 synthetic 搜索/账号条目离线生成。它保留旧媒体结果，并去掉当时不存在的新增字段，用于验证搜索、视频封面、视频详情、账号详情和作品页的严格恢复兼容。当前生产恢复只以正式重放 Raw 的已知旧协议投影核对这些行；Fixture 不参与新内容映射，不接受改动正文、媒体、内容 ID 或 Raw 来源的行。
