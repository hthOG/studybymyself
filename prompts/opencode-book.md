# OpenCode／Muse Spark 的逐節執行提示

此提示補充[start-book](start-book.md)，不取代權威 Skill。先讀[宿主指南](../docs/OPENCODE.md)、[Codex品質基準](../skills/textbook-to-zh-tw-notes/references/codex-quality-baseline.md)、[公式核驗規範](../skills/textbook-to-zh-tw-notes/references/formula-verification.md)。開始寫章稿前讀[逐章規範](../skills/textbook-to-zh-tw-notes/references/chapter-authoring.md)及[局部示範](../examples/codex-style/lesson.md)。

沿用使用者選好的 Muse Spark；先記錄可觀察的宿主能力，不猜模型ID、思考參數或工具名稱。不要讀 `.codex/config.toml` 後宣稱 OpenCode 已套用。分工的角色名稱是任務描述，不是保證存在的宿主 API。

對當前完整小節依序完成：

1. 用一句具體問題確定這節的學習輸出，列前置定義、原書位置與要使用的題圖。缺原式、圖說或原題條件先向來源任務補件。
2. 在公式之前寫清物理情境、符號、單位、觀察者／座標與固定量。每個新量都回答「為了判斷什麼才引入它」。
3. 按原書論證順序寫推導：起始關係→選這個操作的目的→重要中間式→假設在何處使用→所得量的物理解讀。灰框只承接當前卡點，框後回正文；不套印八個小標、不湊字數。
4. 例題先解讀條件並選法，再算符號式、代數值與單位，回答每個問項及結果意義。提示不能當全解；「同理」「見核驗檔」不能取代核心計算。
5. 將正式公式存 `content/math/` 並 input。在 `verification.md` 寫可重算的過程；交給另一任務上下文，讓核驗者先由原頁與前提自行算，再比較作者結果。
6. 依核驗規範完成每個適用物件的 `math-audit.json`；記錄稿件、前置符號及證據的實際SHA。發現矛盾先查約定及原頁，再改公式；候選不能直接作為後文前提。不是將所有status改pass。
7. 主代理接受修正版後，核對敘事和逐題答案是否足夠自學；記下受影響的引用、題解、公式表及圖說並一併複核，保存續點，再開始下一節。

正式交付前從最終PDF檢索與逐頁確認：無「待主代理」「候選訂正」「此處放原圖」「p.?」「不印正式」及工作檔名充當正文；這些字詞若在教學內容確有合理用途，須人工判讀，不能只為消警報刪字。圖若已插入也要清掉殘留位置註記。答案在該章末唯一實際位置，不另印空的指路頁。

內容核驗、公式核驗與PDF逐頁看圖各自有證據；缺一項保留未完成，不以其他項通過抵銷。品質目標是接近使用者認可的Codex寫法，不能承諾任何模型完全零錯，不能宣稱本repo測試等於Muse Spark實機評測。

## 成品與訂正log

依[成品規範](../skills/textbook-to-zh-tw-notes/references/reader-facing-content.md)，代理自行擷取／裁切實際照片與原圖並直接嵌入正文，先產生圖檔再寫includegraphics；不留占位框、檔名框或要求讀者自行插圖。訂正後直接使用採用的公式、數值及解釋，候選、未決策、原錯式、決策過程與完整依據留logs/corrections.md並隨可編輯專案交付；預設不印訂正流程框。背景核驗及狀態紀錄照常。

冊數依使用者指定，不受2–4冊限制；未指定才預設2–4冊。主代理將指定冊數與原話／訊息定位記入book.json的volume_count_request（count、evidence），無需重複確認。每冊全部PDF頁面最多100頁及完整核驗維持；依[分冊契約](../skills/textbook-to-zh-tw-notes/references/book-contract.md)初始化與驗收。
