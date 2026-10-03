# 纳西妲聊天中的研究知识

聊天已接入 `Nahida's file/research/db/research.db` 的已审核知识。重启原来的 `nahida_brain/main.py` 聊天程序后生效，继续使用当前本地 Qwen 服务。没有增加新的安装依赖。

可以直接问：

- “GPT-SoVITS 的 CUDA Graph 优化有实测证据吗？对 RTX 5060 Ti 有效吗？”
- “GPT-SoVITS 的 RTF 0.014 是 issue 作者自己复现的吗？请给出处。”
- 当前话题明确是 GPT-SoVITS 时，短追问“那这些优化的来源呢？”也可以检索。

检索只认已审核主题的名称及常见拼写，例如 `GPT-SoVITS`、`GPT SoVITS`、`GPTSoVITS`。普通闲聊不附加资料；只有简短的技术追问才允许沿用当前话题。这是有限的关键词路由，不是任意语义搜索。目前知识库只有 GPT-SoVITS 速度研究这一审核过的主题。

## 回答如何生成

宿主通过固定 Python 脚本的 `retrieve` 命令读取独立研究库。最新问题经 UTF-8 标准输入传入，不进入命令行参数、研究日志或研究数据库。查询连接使用 SQLite 只读模式，排除草稿、拒绝和撤回的条目，并核对原始快照完整性。

资料作为单独的数据消息放在最新用户消息之前；系统提示只包含可信的处理规则。一次聊天推理让 Qwen 选择最多三条相关知识，本地解码器用 JSON Schema 将输出限制为检索所得的知识 ID。程序只展示这些条目的**审核原句、证据类型、置信度与来源链接**，不展示模型自由生成的技术结论。模型返回格式错误、未知 ID、额外字段或选择接口失败时，程序按问题关键词从已审核条目中选择，不再发起第二次推理；数字按完整小数匹配，避免把 `0.014` 与其他测量混淆，并优先覆盖问题中不同的关注点。没有对应条目时，会说明资料不足。

这是针对本地实测中出现的错误采取的约束：自由回答曾把“应用 CUDA Graph 之前的测量”改写成前后对比，并遗漏来源。选择条目后由程序保留原句，可以防止这些改写进入研究回答。条目选择仍可能不够相关；现有资料也不能覆盖未经捕获的网页、后来更新的实现或本机实验。

“已审核”只表示结论与已捕获来源的关系经过核对。`quoted_claim`、`user_report`、`inference` 等分类仍保留原有证据强度，不表示独立复现或本机性能保证。

## 容量与故障处理

检索 JSON 最多 4000 个 Unicode 字符；资料放入聊天前，使用当前本地 llama.cpp 的 `/props`、`/apply-template` 和 `/tokenize` 检查实际聊天模板的 token 数。总量按实际服务容量和 16384 上限中较小者计算，保留 256 个输出 token 与 256 个余量。检查不会增加模型推理回合或改变服务配置。

数据库缺失、查询超过三秒、快照校验失败、接口不可用或容量不足时，跳过可选研究资料并继续原来的聊天流程。这样的普通回答不具有本地审核证据保障。日志只记录失败类型或退出码，不记录用户问题和子进程输出。

默认启用；要临时关闭，在启动聊天的 PowerShell 窗口中设置：

```powershell
$env:NAHIDA_RESEARCH_KNOWLEDGE = "0"
python nahida_brain/main.py
```

重新启用可将变量设为 `1`，再重启聊天程序。

## 与个人记忆和联网研究的边界

研究查询不写 `nahida_brain/data/nahida.db`，也不写研究使用计数。原有聊天消息仍照常保存；记忆提取发生在研究资料进入回答之前，检索 JSON 不传给记忆提取器。记忆提示也明确要求第三方基准和助手技术建议不得被改写成用户亲自测试或采用的经历。正常对话中助手的已显示回答仍可能出现在后续聊天历史里。

已审核知识检索不启动浏览器或研究任务。实时查询使用下述独立入口；想把新资料变成长期研究知识，仍先运行 `research_runner.py`，再按 [审核说明](../nahida-agent-stack/REVIEWING.md) 批准可信条目。研究容器继续只挂载 `Nahida's file`，不获得 Brain、个人记忆、GPT-SoVITS 或宿主 shell。

## 实时查询

重启 Brain 后默认启用 `src/live_lookup.py`，由宿主调用固定的 `nahida-agent-stack/live_lookup.py`。最新请求先走实际查询入口；取得结果后，由程序显示来源与时间，不交给模型自由编写查询结果。可以问：

- “或者你帮我看看现在 Puchong 的天气如何”——实际查询 Open-Meteo 地名与当前天气。回答注明城市、州、国家、数据时间、时区、查询时间和两个来源链接。这是天气模型估计，不是当地传感器实测；超过三小时的数据不会作为当前天气显示。未来天气预报暂未接入。
- “帮我打开 https://example.com/ 看看”——打开指定公开链接，核对页面 URL 后显示有限原文摘录。需要登录、出现验证页或重定向导致 URL 不匹配时，不接受为有效结果。
- “帮我上网查一下 Puchong 餐厅”——尝试公开网页搜索。**当前实机测试未取得有效餐饮搜索结果**：搜索站点返回访问限制，或与关键词无关的页面。此时只说明失败，不给店名或地址，也没有接入 Google Maps 或点评服务。

“公司附近有什么好吃的”和“来帮我查查看吧”会要求确认城市或街区；只用用户在对话中明确提供的公开查询地点，不把私人工作记忆或助手先前虚构的地址传给研究容器。确认地点后尝试餐饮搜索，但现有实现不证明与公司的距离、口碑、营业状态或开业日期。已询问其他城市天气，不代表公司就在该城市。

控制台出现 `[Live] Starting weather lookup via isolated browser...` 才表示启动实时天气查询；随后 `[Live] Lookup ok; record: ...` 表示取得有效结果，`failed` 表示失败。`[Research] Live web/maps not called; no verified live result.` 则仍表示该轮没有实时结果。追问“你真的查过了吗”或“来源是什么”使用当前会话中的实际执行记录，保留原查询时间，不冒充新查询。换话题或重启后不沿用旧记录。

宿主复用既有容器检查、内部网络、Chromium 和 Squid。所有外部数据仍由无宿主挂载、无个人登录状态的临时浏览器获取；没有新增 Research Agent 的联网 shell 工具。每个查询最多 110 秒、18 次浏览器调用、每页 4000 字符、最多两条来源和 6000 字符输出，不调用研究模型。共享锁避免查询与研究任务争用浏览器；退出时删除本次拥有的浏览器。需要既有 Docker/OpenClaw/本地模型服务就绪，没有新增安装依赖。

原始网页与查询记录只写入 `Nahida's file/research/raw/lookups/<查询ID>/`，不写研究数据库，不自动批准知识。只发送请求的 `kind` 与 `query`，不发送 Brain 提示词、私人记忆或 active context；查询关键词与公开页面会保存在本地查询记录。会话执行记录只在进程内暂存。原有聊天历史仍按 Brain 原流程保存。

可通过 `NAHIDA_LIVE_LOOKUP=0` 关闭实时查询，设回 `1` 再重启可以恢复。关闭后保留诚实的未查询提示。普通模型生成仍收到“本轮未提供实时结果”的能力状态，并检查明显的虚构搜索、手机搜索和按钮操作声明；这些有限的词句检查不能覆盖所有幻觉。记忆提取和每日摘要不会把助手的搜索声明当成用户经历；未删除已有历史或个人记忆。

实机验证天气、公开页面、来源追问与餐饮地点澄清：

```powershell
python nahida_brain/tests/smoke_live_lookup.py
```

该测试使用合成会话，阻止私人数据库连接和回答模型调用，不启动语音。报告位于 `nahida-agent-stack/logs/brain-live-lookup-smoke.json`。研究数据库哈希应保持不变。

关闭实时入口、复现旧虚构历史与正常闲聊的测试：

```powershell
python nahida_brain/tests/smoke_external_grounding.py
```

测试阻止个人数据库连接，只用合成公司背景与合成历史，不启动 TTS。已识别的未支持查询不会调用回答生成模型，原有聊天入口的时间与记忆分析仍照常执行。报告保存在 `nahida-agent-stack/logs/brain-external-grounding-smoke.json`。

## 验证

在项目根目录运行边界测试：

```powershell
python -m unittest discover -s nahida_brain/tests -v
python -m unittest discover -s nahida-agent-stack/tests -v
```

手动实机测试使用两条合成问题、真实已审核研究库与当前本地 Qwen；个人数据库连接被测试保护器阻止，聊天记录、会话、记忆和语音输出均不启动：

```powershell
python nahida_brain/tests/smoke_research_chat.py
```

报告保存在 `nahida-agent-stack/logs/brain-research-smoke.json`。其中记录 token 数、模型选择、最终展示内容、来源、推理次数和研究库未修改校验；这些都是合成测试数据。
