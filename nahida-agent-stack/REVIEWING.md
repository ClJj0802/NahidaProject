# Research 证据审核 V2

研究运行完成后，模型生成的文本仍是草稿。完整运行会自动创建审核清单，并登记独立数据库 `Nahida's file/research/db/research.db`。审核明确批准的条目才进入正式查询。这里的“已审核”表示原文与结论的关系经过核对；用户报告或引用基准不会因此变成独立复现的性能事实。

所有命令均在 `NahidaProject` 根目录执行，使用 Python 3.11+。审核命令使用本地快照，不启动浏览器、Docker 或模型；需要保留对应的 `Nahida's file/research/raw/runs/<运行ID>/` 原始文件。仅保留导出的 Markdown 不能替代这些审核依据。

## 已完成的例子

用户运行 `20261002T160959Z-cf44ea88` 提出了 16 条候选结论。Codex 对照两份原始快照修正并批准了 8 条，拒绝了 8 条。引用基准明确归类为 `quoted_claim`；请求参数和作者测量归类为 `user_report`；实验提案与有限快照内的硬件适用性判断归类为 `inference`。没有批准“CUDA Graph 已启用并达到该 RTF”或“已确认 Windows 调度冲突”的说法。

审核清单：`research/reviews/20261002T160959Z-cf44ea88/packet.json`。

审核后的可读文件：`research/knowledge/reviewed/20261002T160959Z-cf44ea88.md`。其中保留每条结论的证据类型、置信度、审核者、说明、网址、抓取时间、截断标记、原文片段、SHA256 和字符位置。

查询正式知识：

```powershell
python nahida-agent-stack/research_review.py search "GPT-SoVITS"
```

生成供聊天调用的最多 4000 字符上下文：

```powershell
python nahida-agent-stack/research_review.py context "GPT-SoVITS"
```

`context` 返回精简 JSON 字符串；容量不足时省略整条结论并标记 `truncated`，保留完整句子的含义。完整证据可通过对应条目的 ID 和 `search`/审核文件追溯。`search` 默认最多 10 条，可用 `--limit` 调整到 1–20 条；查询字符串最多 300 字符。`context --max-chars` 支持 500–4000 字符。

纳西妲聊天已通过 `retrieve` 调用只读主题检索；该接口从 UTF-8 标准输入接收且仅接受 `{ "text": "用户问题", "active_topic": null }` 两个字段，整个输入最多 16384 字节，`text` 为 1–2000 字符，`active_topic` 为 `null` 或最多 300 字符的字符串。`retrieve --max-chars` 支持 1000–4000 字符，明确匹配已审核主题或有限技术追问后才返回资料；数据库不存在或未匹配主题时返回空的 `knowledge` 列表。Brain 自身使用更小的输入边界，详见 [聊天接入说明](../nahida_brain/RESEARCH.md)。

## 审核新运行

1. 查看运行结束时打印的 `Review packet` 路径。旧的完整运行也可以生成清单：

   ```powershell
   python nahida-agent-stack/research_review.py prepare --run 20261002T160959Z-cf44ea88
   ```

2. 编辑 `packet.json` 的 `claims`。保留全部候选条目、`id`、`section`、`proposed_statement`、`source_keys` 和所有顶层来源信息。可以修正 `statement`，并填写 `decision`、`classification`、`confidence`、`evidence`、`note`。`decision` 使用 `pending`、`approve` 或 `reject`。批准项的修正结论为 10–1200 字符；批准和拒绝都必须填写 5–2000 字符的实质审核说明。批准必须有 1–3 段真实原文；每段长度 20–600 字符，且在对应快照中唯一出现。片段不足以支持结论时，应修正或拒绝，不能仅因为匹配了关键词就批准。

   ```json
   {
     "decision": "approve",
     "statement": "作者报告的现象；注明硬件、计时边界与未验证之处。[S1]",
     "classification": "user_report",
     "confidence": "low",
     "evidence": [{"source": "S1", "quote": "从 sources 的 text 中复制的完整原文片段"}],
     "note": "说明原文如何支持修正后的结论，以及仍有哪些局限。"
   }
   ```

   这是字段示意；示意片段不能通过原文校验。重复出现的片段要扩大到能唯一定位的上下文。网页内容截断时，结论只能涉及已捕获内容。未知的发布日期保持未知，抓取时间不代替发布日期。

3. 检查后应用审核，`--packet` 路径相对于 `Nahida's file`，也支持该工作区内的绝对路径：

   ```powershell
   python nahida-agent-stack/research_review.py check --packet research/reviews/20261002T160959Z-cf44ea88/packet.json
   python nahida-agent-stack/research_review.py apply --packet research/reviews/20261002T160959Z-cf44ea88/packet.json --reviewer your_name
   ```

`check` 只有全部条目校验通过且至少一项为 `approve` 或 `reject` 时才返回 `ready_to_apply: true` 和退出码 0；返回的条目存在 `issues` 或全部仍为 `pending` 时退出码为 2。清单结构、原始依据或文件读取错误会直接停止并返回退出码 1。批准项写入正式知识，拒绝项保留审核记录，`pending` 项继续是草稿。任一条目校验失败时整次审核都不写入，避免部分批准。重复索引、生成清单或提交相同审核不会增加重复记录、清空审核决定或覆盖已有清单。修改已经审核的条目要提交明确的新决定；撤回批准可改为 `reject` 并说明原因，正式查询与导出随之移除该条目。

证据类型可选 `quoted_claim`、`user_report`、`maintainer_statement`、`documentation`、`suggestion`、`inference`。Contributor 身份不能直接等同于维护者。置信度使用 `low`、`medium`、`high`，审核说明应交代它指向文本忠实度还是结论可信度。

## 数据与恢复

数据库使用 `research_runs`、`research_sources`、`research_topics`、`research_knowledge`，以及证据关联表 `research_evidence` 和审核历史表 `research_reviews`。来源按运行保留不可变快照，重复导入同一运行不重复记录。同一作者的重复测量仍需语义审核去重；数据库不把多个网页当成独立验证。

新运行保存 `discovery-sources.md`、`source1-artifact.md`、`source2-artifact.md`、`synthesis-artifact.md`。旧运行使用其目录内的原始模型输出和来源捕获。原文文件或草稿快照改变后，审核与正式查询会停止并报告完整性错误，不能靠再次导入偷偷替换依据。

SQLite 是审核状态的依据，Markdown 是可重建的导出文件。只读查询不会写入聊天记忆或更新使用计数。如果索引失败，运行文件和报告保留，可修复问题后用 `prepare` 重试；失败与分阶段运行可用 `index --run <id>` 登记。若导出失败，可重放同一 `apply`，或执行：

```powershell
python nahida-agent-stack/research_review.py export --run 20261002T160959Z-cf44ea88
```

审核者负责判断语义关系。程序校验片段、来源、边界和状态，不能自动证明实验结果可靠，也不使用另一个 9B 回答来自动批准知识。聊天接入只读取已经批准的条目；定时研究、自动清除和记忆衰减尚未加入。
