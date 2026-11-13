# studybymyself

將一本英文原文教科書，整理成 **2–4 冊繁體中文自學講義，每冊最多 100 頁**。主要供 Windows 本機 Codex 使用；讀者學過基礎微積分。主代理先解析目錄、平行委派子代理閱讀，最後統一教學內容與 PDF。

## 直接交給 Codex

把下面這段交給新的 Codex 工作，填入原書的本機路徑即可：

```text
請取得 https://github.com/hthOG/studybymyself 到一個新的本機資料夾，
先讀 repo 的 AGENTS.md 與 prompts/start-book.md，再按它們執行。
我的原文書：<本機 PDF 絕對路徑>
輸出目錄：<本機資料夾絕對路徑>
處理範圍：整本書。
使用 repo 的子代理設定，主代理只讀目錄、交接及必要的小範圍原文，
平行分派 subagent 分批閱讀、檢索及核對；整理為2–4冊、每冊最多100頁。
必要時執行一鍵環境準備；遵守 Codex 當前權限，完成後交付 PDF、LaTeX 與核驗報告。
```

完整、可重複使用的 [啟動 prompt](prompts/start-book.md) 與 [續作 prompt](prompts/resume-book.md) 已包含講義、分工與檢核要求。先把 repo 開為 Codex 專案，再開始讀原書；若在別處工作，須明確讀入本 repo 的 AGENTS.md，不能假定遠端 URL 的規範會自動生效。

## Windows 一鍵準備

已安裝 Codex 後，在 repo 根目錄執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

安裝流程會檢查 Python 3.11+，需要時透過 WinGet 安裝 Python；建立 repo 專用 `.venv` 並安裝 Python 套件。缺少 XeLaTeX 時透過 WinGet 安裝 MiKTeX，使用 repo 專用 TeX 專案實際測試中文、數學及繪圖套件；既有 MiKTeX 的缺少套件也會透過其套件管理器補齊。優先使用現有 XeLaTeX，不改使用者的 Codex 全域設定。下載與系統安裝仍可能要求 Windows／Codex 批准；遭拒時回報失敗，不繞過。

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

- 主文採有連貫性的教學敘事，先說問題、動機與物理意義，再給定義、公式和應用；術語首次出現保留英文。
- 主文保留關鍵推導，原書的進階推導放灰底框；必要時僅補齊簡易缺步並標記「AI 補齊」。不另外編成延伸教材。
- 每節及來源改變的段落標原書頁碼；詳細書目及核驗過程存在工作資料，不讓正文充滿稽核標籤。
- 儘量保留原圖，不能使用才重繪；圖表均有中文解讀。
- 題目主要採用原書。正文代表例題題後詳解；自測和獨立題的提示、解答放各章末。原書無可用題目才自編。
- 可查證並修正已確認的原書錯誤，修正旁註原書頁碼、修改依據與參考來源；不擴寫額外教材。
- A4、單欄、黑白灰、約11pt、適當留白、框線例題、右側公式編號。100頁包含每冊所有頁面；不以小字塞頁。

完整標準在 [Skill](skills/textbook-to-zh-tw-notes/SKILL.md) 與 [撰寫規範](skills/textbook-to-zh-tw-notes/references/pedagogy.md)。原書分配範圍須由子代理完整閱讀；「有閱讀」與「有全部寫入講義」分開計算，次要內容可依頁數預算壓縮／略過，須列出取捨。

## 流程與檢查

1. 環境檢查 → 書目／目錄／頁碼對照 → 分批任務清單。
2. 子代理平行閱讀／搜尋／術語／圖表回報，主代理對帳與規劃2–4冊。
3. 主代理整合章稿、原書代表題、逐題核驗；每節完成即保存續點。
4. 鎖定內容 → 各冊編譯 → 實際頁數／逐頁視覺 QA → 必要時回到內容取捨。
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

`init` 只抽字建檔，不能自動寫出講義或標記已讀；章節結構、分冊規劃、正式內容與 QA 由代理依契約完成。`book.py check` 會讀實際 PDF 並攔下第五冊、超過100頁、章節配置遺漏、內容變動與不完整視覺紀錄。通過腳本不表示物理內容一定正確。

## repo 結構

```text
AGENTS.md / agent.md             正式代理規範與相容入口
.codex/config.toml               分享的子代理設定
prompts/                        全書啟動、續作、來源子任務、核驗子任務
skills/textbook-to-zh-tw-notes/   可攜 Skill、參考規範、LaTeX模板與檢查器
setup.ps1 / scripts/             Windows環境、doctor與測試工具
docs/                           使用者需求、詳細全書流程與驗證說明
```

repo 自身已可被明確讀取使用，不必把檔案安裝到全域 Skills 才能執行。需要 Skill 清單自動探索時，依目前 Codex 的 Skill 安裝機制另行安裝 `skills/textbook-to-zh-tw-notes`；repo 的 AGENTS.md 仍是分工與專案設定入口。

## 測試與限制

```powershell
.\.venv\Scripts\python.exe scripts\validate_repo.py
.\.venv\Scripts\python.exe -m unittest discover -s skills\textbook-to-zh-tw-notes\tests -v
```

驗證範圍與尚未驗證之處見 [VALIDATION](docs/VALIDATION.md)。這是代理執行規範與輔助工具，沒有聲稱已完成真實原書測試。環境安裝器的實際完整系統安裝另列驗證狀態，不用模擬測試冒充。

原書與工作資料放在 repo 外或被忽略的 `inputs/`、`books/`。提供的八張照片只用來提取教學／版面偏好，未收入本 repo。上游方法與 MIT 授權見 [來源說明](skills/textbook-to-zh-tw-notes/references/provenance.md)。
