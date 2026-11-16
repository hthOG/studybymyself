# 給 Codex 的 prompt

```text
請接手「Muse閱讀、Codex寫作＋排版」分工。
私人交接包：<包含START-HERE.md的資料夾絕對路徑>
Codex新工作區：<交接包及workflow repo外的全新本機資料夾>
請先讀包內START-HERE.md、workflow/AGENTS.md及workflow/workflows/muse-codex/README.md，
再讀project/handoff-notes.md、handoff-materials.json與handoff.json。
使用包內workflow/workflows/muse-codex/handoff.py先check，再prepare到上述新工作區；正式書籍專案為其中project/，規範工具為workflow/，
原書副本為original/book.pdf。環境準備只在新的workflow/執行，保留交接包凍結。
原文書已實際附在original/book.pdf，請核對SHA；不依賴Muse聊天記憶或其電腦原路徑。

接受來源前核對目錄、完成範圍、原頁／公式／原圖／題面與相依條件。
checkpoint只表示部分交接，對缺漏完成有界補讀；不能把尚未讀完當整書完成。
已接受且版本未變的閱讀成果可重用，主代理不載入整書原文。
舊章稿、QA、math-audit與編譯pass僅作歷史，不能直接算新正文核驗通過。

由你負責正式中文內文、推導與題解、選題取捨、術語整合、獨立驗算、LaTeX與PDF。
依共用Skill、逐章編寫prompt、四冊Codex品質基準、中文解釋規範與成稿示範，
從來源證據重新組織教材，寫出自然、完整、能自學的說明。
先建立問題、物理意義、定義和符號，再就地引入公式，補清必要推理與代入計算，
解釋結果並給完整題解；不要保留Muse草稿的公式堆疊或生硬工作紀錄口吻。
逐項做原頁辨識、獨立重算及適用條件檢查，保留實際核算證據，不照收Muse結論。
原圖／照片直接嵌入，不要占位。PDF不列學習目標、先備清單、作者檢查點及製作指令。
訂正後直接採用結果，訂正依據與過程保存在logs/corrections.md。
不增加原書外延伸教材。冊數依我的指定；未指定預設2–4冊，每冊全部PDF頁面最多100頁。
完成teaching、內容鎖、正式編譯及每冊全部頁面的實際視覺檢查後，
交付最終PDF、可編輯專案、來源對照、選題／刪節清單、訂正log與品質報告。
私人原書和交接資料保留本機，不提交公開GitHub。
```

## Goal

```text
接受Muse的可回查來源交接，由Codex完成接近使用者認可之四冊《黑洞物理導論》品質的
繁體中文自學講義：自然連貫的正文、足夠的推理與完整題解、實際原圖、逐項獨立核算、
清楚的LaTeX排版與各冊全頁PDF檢查；交付成品及完整可編輯專案，不把內部製作語印給讀者。
```
