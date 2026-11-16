# studybymyself

正文以[中文解釋規範](skills/textbook-to-zh-tw-notes/references/prose-and-explanation.md)及[完整成稿](examples/reader-prose/lesson.md)為準：自然完整句、公式就地引入、推導與解答走得通。學習目標、讀完應能、先備清單及作者檢查點只留內部，不印PDF。具體差異見[兩冊可讀性比較](docs/READABILITY-2026-11-16.md)。


成品圖片直接嵌入實際照片／原圖，不留占位；訂正後直接使用採用的公式與數值，候選、未決策及訂正過程留在隨專案交付的 `logs/corrections.md`。詳見[成品呈現規範](skills/textbook-to-zh-tw-notes/references/reader-facing-content.md)。

## OpenCode／Muse Spark：以 Codex 講義為品質基準

現行標準是使用者認可的四冊 Codex《黑洞物理導論》，不融合 vol 版本的優點。具體寫法與有頁碼的觀察在[品質基準](skills/textbook-to-zh-tw-notes/references/codex-quality-baseline.md)；原PDF、頁面圖與全文不隨repo上傳。舊84頁講義／照片僅保留為可選歷史參考，與下方舊說明衝突時依現行基準。

OpenCode使用者從[宿主指南與可貼上提示](docs/OPENCODE.md)開始，再依[逐節執行提示](prompts/opencode-book.md)製作。在repo根啟動，原有AGENTS.md與新增opencode.json載入共用規範；原生技能入口在.opencode/skills，實際內容仍只有skills/下的一份。沿用已選的Muse Spark，不改供應商、金鑰、權限或Codex設定，也不猜模型ID。

本次新增三個具體支援：

- [完整局部成稿](examples/codex-style/lesson.md)：用自造來源展示問題、定義、逐步推導、結果解讀與完整練習答案，並有[可執行復算](examples/codex-style/verify.py)。不把它冒充原書內容。
- [公式核驗規範](skills/textbook-to-zh-tw-notes/references/formula-verification.md)與math_audit.py：原頁辨識、獨立重算、約定／量綱／極限／域、訂正與下游重核，逐項綁定正文及證據版本，已接入teaching及內容鎖。
- pdf_text_audit.py：從最終PDF協助找未決訂正、占位、內部交接與未完成核驗文字，逐項回到實際頁人工判讀。

常用檢查（先依下方方式準備repo本機Python環境）：

```text
python examples/codex-style/verify.py
python skills/textbook-to-zh-tw-notes/scripts/math_audit.py init <書籍專案>
python skills/textbook-to-zh-tw-notes/scripts/math_audit.py check <書籍專案>
python skills/textbook-to-zh-tw-notes/scripts/pdf_text_audit.py <最終PDF>
```

math_audit init在選題、正文落點及covered/compressed清單建立後執行，只產生pending模板，不覆寫舊檔。舊專案需補真實有效的核驗紀錄；工具通過只表示紀錄完整且版本對應，不代表公式已被機器證明正確。未完成原頁辨識、獨立核算或最終逐頁看圖時不能宣稱完成。測試狀態見[VALIDATION](docs/VALIDATION.md)；尚未以Muse Spark實機跑完整本書，不能承諾零錯。


將一本英文原文教科書，整理成 **預設2–4冊繁體中文自學講義；使用者指定冊數時依指定，不受2–4冊限制。每冊最多100頁**。可在 Windows 或 Ubuntu 的 Codex 環境使用；讀者學過基礎微積分。主代理先解析目錄、平行委派子代理閱讀，最後統一教學內容與 PDF。

## 直接交給 Codex

把下面這段交給新的 Codex 工作，填入原書的本機路徑即可：

```text
請取得 https://github.com/hthOG/studybymyself 到一個新的本機資料夾，
先讀 repo 的 AGENTS.md 與 prompts/start-book.md，再按它們執行。
我的原文書：<本機 PDF 絕對路徑>
輸出目錄：<本機資料夾絕對路徑>
處理範圍：整本書。
使用 repo 的子代理設定，主代理只讀目錄、交接及必要的小範圍原文，
平行分派 subagent 分批閱讀、檢索及核對；冊數依使用者指定，未指定則預設2–4冊；每冊最多100頁。
必要時執行一鍵環境準備；遵守 Codex 當前權限，完成後交付 PDF、LaTeX 與核驗報告。
```

[全書啟動 prompt](prompts/start-book.md)負責從閱讀到交付；[逐章編寫 prompt](prompts/write-chapter.md)直接規定章稿如何寫。寫作前必讀[編寫操作規範](skills/textbook-to-zh-tw-notes/references/chapter-authoring.md)，首次寫章稿時讀[中文成稿示範](examples/reader-prose/lesson.md)：含自造來源與兩個連貫小節，示範概念、公式、計算與結果如何銜接；示範內容不得移入真實原書。[續作 prompt](prompts/resume-book.md)處理中斷續接。先把 repo 開為 Codex 專案，再開始讀原書；若在別處工作，須明確讀入本 repo 的 AGENTS.md，不能假定遠端 URL 的規範會自動生效。

想先看 agent 是否真的能照規範編寫，可讀[實際試寫與審閱](examples/authoring-trial/README.md)。同一份兩頁自造英文來源另有[詳細版章稿](examples/authoring-trial/detailed/chapter.tex)及[章末完整解答](examples/authoring-trial/detailed/answers.tex)：補清模型條件如何用於推導、積分常數與邊界代入、方向／單位判讀及逐問解題。詳細版已由獨立代理審閱，Windows XeLaTeX 兩次編譯為 5 頁，全部頁面均已渲染並檢視。原有 3 頁試寫及其歷史紀錄保留；這些有界試驗與正式原書全書驗收分開記錄。

## Ubuntu與其他平台

Ubuntu24.04+可使用Codex CLI／提供子代理功能的宿主，在repo執行：

```bash
bash setup.sh --dry-run
bash setup.sh
.venv/bin/python scripts/doctor.py --strict
```

安裝器使用官方apt套件、TeX Live、Noto CJK字型及repo專用venv；只有系統安裝步驟需要sudo。`--check-only`只檢查，`--skip-system`供已備妥系統工具的環境。Ubuntu22.04預設Python不足3.11時須先備妥新版，不自動加入PPA。其他Linux／macOS可手動準備依賴；平台命令、大小寫與搬移流程見[平台指南](docs/PLATFORMS.md)。

## Windows 一鍵準備

已安裝 Codex 後，在 repo 根目錄執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

安裝流程會檢查 Python 3.11+，需要時透過 WinGet 安裝 Python；建立 repo 專用 `.venv` 並安裝 Python 套件。缺少 XeLaTeX 時透過 WinGet 安裝 MiKTeX，使用 repo 專用 TeX 專案實際測試中文、數學及繪圖套件；既有 MiKTeX 的缺少套件也會透過其套件管理器補齊。優先使用現有 XeLaTeX，不改使用者的 Codex 全域設定。下載與系統安裝仍可能要求 Windows／Codex 批准；遭拒時回報失敗，不繞過。

MiKTeX 流程先檢查核心／套件更新，避免舊基本安裝版搭配新中文套件；一次查詢套件狀態，只安裝缺少項目，包含灰框及交叉引用的間接依賴，並明確建立 XeLaTeX 格式檔。2026-11-14 已在使用者授權的 Windows 實機補齊環境，成功重跑安裝入口、嚴格環境檢查及中文模板編譯；乾淨電腦的完整 WinGet 流程尚未另測。

無 WinGet／Python、網路被限制或使用者既有 TeX 發行版缺少套件時，腳本給出具體失敗步驟，不能假報已備妥。安裝 Python／MiKTeX 後若 PATH 尚未更新，腳本會重讀使用者與系統 PATH。可預覽安裝動作或只查環境：

```powershell
.\setup.ps1 -WhatIf
.\setup.ps1 -CheckOnly
.\.venv\Scripts\python.exe .\scripts\doctor.py
```

PDF 渲染使用 PyMuPDF，不另外依賴 Poppler；OCR 不在一鍵套件中，掃描頁由具備視覺能力的子代理逐批讀取／覆核，或使用本機已備妥的 OCR。腳本抽字不代表完成閱讀。

## 確認子代理設定

[.codex/config.toml](.codex/config.toml) 分享的是作者本機現有設定：

| 項目 | 值 |
|---|---|
| 子代理啟用 | `true` |
| 併發子執行緒上限 | `15` |
| 預設子代理模型 | `gpt-6.1-terra` |
| 預設子代理 effort | `medium` |

原環境沒有另外的自訂角色 TOML，因此本 repo 的「來源閱讀／核驗」角色是任務分工，不偽造既有自訂代理。可用模型、實際工具槽位及上限依執行環境；15 是設定上限，不是保證可同時執行15個。`doctor.py` 可核對分享設定，不能證明正在執行的 Codex 已載入它。

Codex 是否載入專案設定也受其信任與管理設定影響，主代理須檢查實際可用工具；不要強制覆寫別人的全域設定。主代理在 medium／high 間依任務選擇，但文字 prompt 不是切換 API：有宿主控制能力才實際調整，否則記錄建議與實際設定。依據：[官方子代理設定](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[官方設定參考](https://learn.chatgpt.com/docs/config-file/config-reference)。

## 講義的寫法

現行品質依四冊Codex黑洞講義；完整84頁物理化學講義及照片僅保留作可選歷史參考。它不是頁數目標、深度上限或原書來源，檔案、頁面影像與原文均不納入 repo。先前提供的13張範本照片只是可選模式的補充參考，已整理於[教學模式](skills/textbook-to-zh-tw-notes/references/reference-patterns.md)：包括公式間的理由、微積分灰框接回原題、模型與圖形比較、完整表格和挖空自測、概念題到情境應用，以及不同數學量、公式與空間分圖、敘述型現象的機制與表格證據。照片頁碼不冒充未來原書；詳細核心解釋與頁數取捨標準見[編寫操作規範](skills/textbook-to-zh-tw-notes/references/chapter-authoring.md)。

- 主文採有連貫性的教學敘事，先說問題、動機與物理意義，再給定義、公式和應用；術語首次出現保留英文。
- 主文保留關鍵推導，原書的進階推導放灰底框；必要時僅補齊簡易缺步並標記「AI 補齊」。不另外編成延伸教材。
- 每節及來源改變的段落標原書頁碼；詳細書目及核驗過程存在工作資料，不讓正文充滿稽核標籤。
- 儘量保留原圖，不能使用才重繪；圖表均有中文解讀。
- 題目主要採用原書。正文代表例題題後詳解；自測和獨立題的提示、解答放各章末。原書無可用題目才自編。
- 題後詳解的示範題與章末才揭答的練習分別使用 examplebox／selftestbox；數學補步限當前卡點，灰框後要寫回原題代入和結果。正式比較表須完整，自測挖空另標並提供章末完整答案。
- 可查證並修正已確認的原書錯誤，修正旁註原書頁碼、修改依據與參考來源；不擴寫額外教材。
- A4、單欄、黑白灰、約11pt、適當留白、框線例題、右側公式編號。100頁包含每冊所有頁面；不以小字塞頁。

核心深度標準在[逐章編寫操作規範](skills/textbook-to-zh-tw-notes/references/chapter-authoring.md)，教學邊界與分類見[教學規範](skills/textbook-to-zh-tw-notes/references/pedagogy.md)。原書分配範圍須由子代理完整閱讀；「有閱讀」與「有全部寫入講義」分開計算，次要內容可依頁數預算壓縮／略過，須列出取捨。

## 適度減少用量

詳細規則在[省量與成果重用](skills/textbook-to-zh-tw-notes/references/efficiency.md)。主要避免同區段重複派工、每次重載全部規範、續作重讀已完成章與無關修訂重做驗算。保留首次完整來源閱讀、獨立核驗及最終各冊全頁視覺QA，不改你的子代理模型／effort與15條上限。

主代理維護任務索引，可用reuse.py封存已接受任務的來源／稿件／證據指紋；變更只退回相關依賴，不能用摘要冒充已讀。約2–4個有界批次起跑，依資源調整；更多並行不是更多免費額度。抽字、編譯、頁數與log篩選交本機工具。這些規則尚未做真實原書省量對照，不承諾固定百分比。

## 流程與檢查

1. 環境檢查 → `book.py init` → 人工核對完整TOC，填妥並驗證 `toc.json`（含原始PDF SHA、逐章source units及有證據的nonchapter排除；原PDF每頁都須有unit）→ 分批任務清單。
2. 子代理平行閱讀／搜尋／術語／圖表回報，主代理對帳，依使用者指定冊數規劃；未指定則預設2–4冊。
3. 主代理整合章稿、原書代表題、逐題核驗；寫作與已完成小節的語意核驗可並行，每節完成即保存續點。
4. Teaching 與內容鎖完成後才做正式編譯。編寫期間可在獨立 draft 目錄編譯工作稿；draft PDF 不建立正式成功收據，也不代表可進入 release。正式各冊編譯後做實際頁數／逐頁視覺 QA，必要時回到內容取捨。
5. 交付所有冊PDF、LaTeX專案、來源對照、選題／刪節清單與品質報告。

常用命令（`<P>` 是本機書籍專案，並非 repo 根）：

```powershell
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\book.py init --pdf "C:\books\book.pdf" --out "<P>" --volumes 2
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\render.py source "<P>" --units u0001-u0005
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\project.py check "<P>" --stage teaching
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\book.py write-layouts "<P>"
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\project.py lock "<P>"
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\book.py compile "<P>"
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\book.py prepare-review "<P>"
.\.venv\Scripts\python.exe skills\textbook-to-zh-tw-notes\scripts\book.py check "<P>"
```

單章專案使用 `project.py compile`、`project.py prepare-pdf-review` 與 `project.py check --stage release`；若專案有 `book.json`，單 PDF 編譯、準備審查及 release 入口會拒絕執行，必須使用上述 `book.py` 多冊流程。

正式編譯會以 XeLaTeX recorder (`.fls`) 記錄實際讀入檔案，使用新的隔離輸出目錄，至少完成兩次穩定編譯，並將成功／失敗狀態、鎖檔、版面、輸入清單及 PDF／log／recorder 雜湊寫入 build receipt。`prepare-review` 驗證receipt後，會從最終PDF以PyMuPDF本機render逐頁PNG及manifest，記錄PDF/receipt SHA、頁數、渲染參數、頁碼對應與每圖SHA，並清空舊notes；release核對全部雜湊與映射，不重render，仍要求人實際逐頁記觀察，機器不自動pass。普通 `render.py pdf` 是draft，只輸出not_reviewed圖。缺少toc ledger或舊receipt/preview格式時fail closed；補核TOC、保留有效teaching核驗、重鎖並重編／prepare，不必重讀未變且已核驗的原書內容。雜湊偵測一般檔案變更，不是抵禦使用者重寫所有紀錄的加密簽章。

`init` 只抽字建檔，不能自動寫出講義或標記已讀；章節結構、分冊規劃、正式內容與 QA 由代理依契約完成。`book.py check` 會讀實際PDF並攔下未核TOC、章映射／來源unit覆蓋缺漏、未記錄使用者指定卻超出預設2–4冊、冊數與使用者指定不符、超過100頁、未被實際編譯讀入的內容落點、內容變動與不完整預覽manifest/視覺紀錄。TOC是否完整、教學內容是否正確及頁面實際品質仍需人工核對。

## repo 結構

```text
AGENTS.md / agent.md             正式代理規範與相容入口
.codex/config.toml               分享的子代理設定
prompts/                        全書啟動、續作、來源子任務、核驗子任務
skills/textbook-to-zh-tw-notes/   可攜 Skill、參考規範、LaTeX模板與檢查器
setup.ps1 / setup.sh / scripts/  Windows／Ubuntu環境、doctor與測試工具
docs/                           使用者需求、詳細全書流程與驗證說明
```

repo 自身已可被明確讀取使用，不必把檔案安裝到全域 Skills 才能執行。需要 Skill 清單自動探索時，依目前 Codex 的 Skill 安裝機制另行安裝 `skills/textbook-to-zh-tw-notes`；repo 的 AGENTS.md 仍是分工與專案設定入口。

## 測試與限制

```powershell
.\.venv\Scripts\python.exe scripts\validate_repo.py
.\.venv\Scripts\python.exe -m unittest discover -s skills\textbook-to-zh-tw-notes\tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

驗證範圍與尚未驗證之處見 [VALIDATION](docs/VALIDATION.md)。這是代理執行規範與輔助工具，沒有聲稱已完成真實原書測試。環境安裝器的實際完整系統安裝另列驗證狀態，不用模擬測試冒充。

原書與工作資料放在 repo 外或被忽略的 `inputs/`、`books/`。提供的完整講義與範本照片只用來提取教學／版面偏好，未收入本 repo。上游方法與 MIT 授權見 [來源說明](skills/textbook-to-zh-tw-notes/references/provenance.md)。

冊數規則：預設2–4冊；使用者指定時依指定冊數（例如1冊或5冊），每冊仍最多100頁。初始化使用 `book.py init --pdf <原書.pdf> --out <新專案> --volumes 5 --volume-count-request "使用者指定5冊"`；主代理記錄真實要求，不另向使用者重複確認。資料格式、續作及內容鎖規則見[分冊契約](skills/textbook-to-zh-tw-notes/references/book-contract.md)。

可採用[Muse閱讀、Codex寫作與排版](docs/MUSE-CODEX-HANDOFF.md)：以可回查的原頁、公式、圖與題目資料包交接，由Codex整合正文並獨立核算；不以聊天摘要或舊pass代替證據。這是可選分工，不更改既有模型設定。
