# OpenCode／Muse Spark 製作入口

本指南補上宿主差異；教學、來源與驗收仍使用同一套 Skill。最新品質基準是使用者認可的四冊 Codex《黑洞物理導論》，詳見[品質基準](../skills/textbook-to-zh-tw-notes/references/codex-quality-baseline.md)。vol 兩冊只用來辨識待改善問題，不作風格或內容優點的來源。

## 啟動與能力確認

更新repo後關閉並重新啟動OpenCode，讓新設定重新載入；在本 repo 根目錄啟動。根目錄 `AGENTS.md` 是共同工作規範；`opencode.json` 只追加本指南，不更改模型、供應商、權限或金鑰。`.opencode/skills/` 的薄入口會引導讀取 `skills/` 的唯一權威版本，不複製整份 Skill。

使用 OpenCode 的 `/models` 從**本機已連線的供應商清單**選擇使用者既有的 Muse Spark；記錄實際 provider/model ID、OpenCode 版本及可取得的參數。顯示名稱不能當 API ID，不猜 `muse-spark` 的供應商前綴，不把 Codex 的 `gpt-6.1-terra`、effort 或15槽位寫進 OpenCode。模型切換是否生效以宿主回報為準；未知就記 null。本 repo 未附供應商設定或認證，也未宣稱已對 Muse Spark 實機跑完整本書。

先確認實際提供：讀寫檔案、Python、XeLaTeX、原頁影像、子代理工具。OpenCode 子代理與 Codex collaboration API 不同，依安裝版本使用可用的任務／子代理介面。讓主代理維持一個小節的整合範圍，閱讀者負責有界原頁，獨立核驗者在另一任務上下文重算；即使同一模型，也不能只讓作者重讀自己的推導後稱獨立核驗。

不要假設一般讀檔工具能看 PDF。先渲染 PNG，再由支援圖片的實際工具／代理看圖，並記錄實際檢視頁。若 Muse Spark 的當前連線不能讀圖片，可沿用有效的原頁視覺交接；缺少交接且無圖像工具時完成能做的抽字、建檔及草稿，保持視覺核驗待辦，不能以文字抽取代替。子代理不可用時保留來源分批計畫，不能改由主代理載入整本書。

在書籍專案的 `progress.json` 記 `runtime`：host、version、requested_model、actual_model、actual_parameters、subagents_available、image_review_available。這是觀察紀錄，不能把期望值抄成實際值。跨平台環境依[平台指南](PLATFORMS.md)準備。

## 可直接貼上的啟動文字

```text
請使用這個 repo 的規範製作整本書，不只做規劃。
原書：<英文原書PDF絕對路徑>
輸出：<獨立書籍專案絕對路徑>
先讀 AGENTS.md、docs/OPENCODE.md、prompts/start-book.md 與權威 Skill。
沿用我在 OpenCode 選好的 Muse Spark，記錄實際模型與能力，不修改供應商或全域設定。
以四冊 Codex 黑洞物理導論的教學品質為基準；讀 references/codex-quality-baseline.md、
references/formula-verification.md 與逐章編寫規範，使用 prompts/opencode-book.md。
主代理只看目錄、有界交接及必要局部原頁；按完整小節分派來源閱讀與獨立核驗。
先清楚說問題與符號，再逐步推導、解讀結果、完整解題；不是把更多公式堆在一起。
每個選入的重要公式／題解都要原頁辨識與獨立復算，修正後重新核驗下游。
冊數依使用者指定；未指定時完成2–4冊，每冊全部PDF頁面最多100頁，以及LaTeX、來源對照、取捨和品質報告。
候選訂正、待辨符號、缺解題、占位文字或內部交接未清完時，不宣稱正式完成。
```

## 每節如何執行

1. 來源任務依 `prompts/source-reader.md` 交付原頁定位、可編輯公式、條件、圖與題，主代理先驗交接再編寫。無圖／符號不清時補件。
2. 主代理依 `prompts/write-chapter.md` 寫連貫正文，先處理一節完整理解鏈；使用[局部示範](../examples/codex-style/lesson.md)校準理由與解讀的密度。該示範是自造測試，不能冒充原書頁碼。
3. 另派核驗任務依 `prompts/verifier.md` 和[公式核驗規範](../skills/textbook-to-zh-tw-notes/references/formula-verification.md)核原頁、重算及記證據，作者繼續下一節。修正的公式、前提與題目都回查受影響範圍。
4. 主代理整合 `math-audit.json`，執行 `math_audit.py check`，再通過原有 teaching、lock、compile、prepare-review、逐頁看圖與 `book.py check`。機器驗證證據對應及版本，不能判定物理真偽或證明人確實讀過。

核心公式不清時不猜；非核心未解來源數值可依來源及選題規則移除其定量主張，明列略過理由與影響，重新核驗剩餘主線；不能只刪除疑點紀錄。不能用「高確定度」「兩次回答一致」「成功編譯」作為正確證據。

## 官方介面依據

於2026-11-15查閱 [Rules](https://opencode.ai/docs/rules/)、[Agent Skills](https://opencode.ai/docs/skills/)、[Agents](https://opencode.ai/docs/agents/)、[Models](https://opencode.ai/docs/models/)。介面隨版本變動時以當前官方文件與本機實際工具為準。本專案未新增自動同意權限，也不把其他宿主的設定檔當作 OpenCode 設定。

## 成品圖片與訂正（使用者補充）

依[成品規範](../skills/textbook-to-zh-tw-notes/references/reader-facing-content.md)，由代理直接擷取並嵌入真正照片／原圖，不留占位。正文呈現採用後公式與數值，不印候選、未決策及內部訂正過程；詳細紀錄在書籍專案logs/corrections.md，隨LaTeX專案一併交付供使用者查找。核驗仍在背景執行，不把log狀態印成教材。
