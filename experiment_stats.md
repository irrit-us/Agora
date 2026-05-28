# 实验数据统计

## 指标说明

- **(b) 可解析 TEST RESULT 闭环次数**：仅当本轮走「新测实现」路径且最终响应里能解析出标准 `TEST RESULT` 块时 +1；相似测例分支、TestGen 报错或输出格式不符时不会增加，可能与「实际写文件 / 跑测」不一致。
- **有效测试完成次数**：由 orchestrator 在运行时写入（`meaningful_test_runs`）。仅当 **解析结果为 PASS** 或响应中含 **`<confirmed_bug>`** 时计一次；TestGen/HTTP 报错、空输出、解析失败、以及 **FAIL 但未标 confirmed_bug** 均不计。**旧版会话 JSON 无该字段，统计为 0**；需重新跑实验才有值。
- **(b′) Strategy API 调用次数**：metrics 中 `agent_type=strategy` 的 LLM 调用总数（含 bug exploitation 阶段的 strategy）。
- **写入测试文件数 / action log 命令次数**：由同会话的 `action_logs/session_YYYYMMDD_HHMMSS.log` 解析（与 `metrics/session_*.json` 按秒级时间戳对齐）；路径缺失或日志不存在时为 N/A。命令次数包含编译失败、反复调试等，**不等于**上面的「有效测试完成」。

### go-ethereum

| 指标 | GPT 5.2 | Claude Sonnet 4.5 | Gemini 3.1 Pro |
| ------ | ---: | ---: | ---: |
| 会话状态 | completed | error | error |
| (a) Bug 数量 | 6 | 3 | 2 |
| (b) 可解析 TEST RESULT 闭环次数 | 6 | 4 | 1 |
| 有效测试完成次数（PASS 或确认 bug） | 0 | 0 | 0 |
| (b′) Strategy API 调用次数 | 17 | 11 | 6 |
| Similarity API 调用次数 | 430 | 119 | 84 |
| TestGen API 调用次数 | 526 | 183 | 36 |
| 写入测试文件数（action log，*_test.go 去重） | 17 | 16 | 1 |
| action log：`go test` 等命令次数（含失败/重试，非语义） | 73 | 89 | 8 |
| (c) Tokens/Bug | 9,456,425 | 5,207,171 | 25,809,204 |
| (d) API 调用次数 | 1,955 | 708 | 1,265 |
| (e) 总花费 | $29.58 | $54.21 | $19.13 |
| (f) 总 Token 数 | 56,738,548 | 15,621,513 | 51,618,408 |
| (g) API 调用/Bug | 325.8 | 236.0 | 632.5 |
| (h) Token/Bug | 9,456,425 | 5,207,171 | 25,809,204 |

### avalanchego

| 指标 | GPT 5.2 | Claude Sonnet 4.5 | Gemini 3.1 Pro |
| ------ | ---: | ---: | ---: |
| 会话状态 | completed | error | error |
| (a) Bug 数量 | 0 | 3 | 0 |
| (b) 可解析 TEST RESULT 闭环次数 | 6 | 3 | 0 |
| 有效测试完成次数（PASS 或确认 bug） | 0 | 0 | 0 |
| (b′) Strategy API 调用次数 | 33 | 7 | 1 |
| Similarity API 调用次数 | 935 | 67 | 52 |
| TestGen API 调用次数 | 902 | 141 | 977 |
| 写入测试文件数（action log，*_test.go 去重） | 6 | 17 | 0 |
| action log：`go test` 等命令次数（含失败/重试，非语义） | 36 | 98 | 0 |
| (c) Tokens/Bug | N/A | 4,800,476 | N/A |
| (d) API 调用次数 | 1,870 | 735 | 1,030 |
| (e) 总花费 | $16.51 | $49.91 | $95.03 |
| (f) 总 Token 数 | 35,757,693 | 14,401,427 | 220,801,721 |
| (g) API 调用/Bug | N/A | 245.0 | N/A |
| (h) Token/Bug | N/A | 4,800,476 | N/A |
