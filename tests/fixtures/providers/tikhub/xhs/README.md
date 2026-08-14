# TikHub 小红书测试 Fixture

`search_notes_page1.sanitized.json` 来源于项目 Owner 于 2026-08-05 使用 TikHub Xiaohongshu App V2 `search_notes`、关键词“爱玛”、`page=1`、`sort_type=time_descending`、`note_type=不限`、`time_filter=一天内`、`source=explore_feed` 取得的真实成功响应。

该 Fixture 只保留验证 Provider Operation、分页和 Mapper 所需的结构与字段类型；提交前已替换真实笔记 ID、账号 ID、昵称、标题和正文，并删除 `xsec_token`、缓存签名 URL、CDN 签名 URL、调试令牌和其他不参与当前 Contract 的供应商私有字段。它用于证明已观察到的 App V2 搜索响应结构，不代表详情/评论接口的真实兼容验收。

真实付费 Probe 默认不进入 CI；API Key 不允许写入本目录、源码、日志、Raw Fixture 或 Git 历史。
