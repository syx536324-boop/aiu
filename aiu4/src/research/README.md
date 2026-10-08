# 论文发现与阅读

`Discovery.search/import/latest` 负责官方目录、扩展索引、检索证据与候选；`Library.list/add/collect/read/collectMany` 管文献与按页正文；`Reviews.save/list` 保存结构化阅读草稿。`paperTools` 把接口公开给 Pi。

官方目录成功缓存 24 小时，元数据成功检索缓存 1 小时。领域筛选在本模块，前端只显示结果。重点会议只是初筛；质量判断必须结合正文证据。

`download.mjs` 的 `downloadPdf(url, signal, progress)` 负责受限公开来源下载；`allowedPdf` 校验初始地址和每次重定向。等待响应限 30 秒，收到响应后传输限 180 秒，单 PDF 限 40MB，整项任务仍受 600 秒上限约束。进度显示已接收大小，错误保留服务器名与原因。重试优先使用上次未失败的来源。

YOLO 原论文补充作者主页 https://pjreddie.com/ 的公开 PDF https://pjreddie.com/static/papers/yolo_1.pdf （2026-10-07 核对），只放行该文件路径。作者官网版本与会议版本分别标注，正式发表来源继续指向 CVF。
