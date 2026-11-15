# 給 Codex／OpenCode 的續作 Prompt

請讀AGENTS.md與Skill的references/efficiency.md；只在規範變動／首次接手時補讀prompts/start-book.md相關階段，從這個既有書籍專案續作：<專案絕對路徑>。

先核對source.json原檔SHA、book.json章表與分冊、progress.json任務波次與未解事項，再按需讀子代理交接索引。主agent不得讀全書；不要重新建檔覆寫已完成內容。重用現有任務與子代理設定，只有失效來源／待補件／修改後受影響範圍才重新派工。

進入未完成的章稿時讀prompts/write-chapter.md及Skill的references/chapter-authoring.md對應步驟；檢查既有稿是否只有大綱／公式／答案，若有就記缺口並補正文，不把舊pass當教學完成。依目前續點完成所有剩餘章與各冊檢查，保留2–4冊、每冊全頁數≤100的限制；次要內容取捨要留selection-log。若來源或內容鎖變動，作廢相應核驗及PDF視覺紀錄，核對後再編譯。交付完整成果或具體未完成狀態，不把前次完成宣告當本次驗證。

續作前檢查tasks/index.json及reuse.py check結果；有效來源交接不重新讀整章，核驗結果則另核稿件／公式／前置定義依賴。原檔路徑跨平台搬移須重核SHA並依平台指南重建環境／內容鎖；新編譯PDF重新逐頁看圖。

OpenCode續作先讀[宿主指南](../docs/OPENCODE.md)，沿用使用者已選Muse Spark，不套Codex TOML。新版本另檢math-audit.json及其稿件／前置定義／證據指紋；舊專案缺ledger時依[公式核驗規範](../skills/textbook-to-zh-tw-notes/references/formula-verification.md)補真實有效證據，不捏造pass、不重讀未變全書。
