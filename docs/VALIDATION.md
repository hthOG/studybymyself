# 驗證範圍與重現方式

本文件區分程式／規範檢查與實際原書教學驗收。機器測試使用合成PDF與追蹤資料，不能證明有人看過圖、推導成立或中文講義可自學。

## 可重現命令

```powershell
.\.venv\Scripts\python.exe scripts\validate_repo.py
.\.venv\Scripts\python.exe -m unittest discover -s skills\textbook-to-zh-tw-notes\tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\setup.ps1 -WhatIf
.\setup.ps1 -CheckOnly
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Ubuntu對應入口為`.venv/bin/python`；安裝預覽為`bash setup.sh --dry-run`，只查環境為`bash setup.sh --check-only`。測試環境有Bash時會執行安裝器模擬流程測試；沒有Bash則明示skip，不能把skip算成通過。Windows可設定`BASH_EXECUTABLE`為已安裝Git Bash的完整路徑。

包含來源抽字不等於已讀、缺頁／缺圖／未核來源、引用落點、公式／來源證據／全書規劃鎖、不同冊的答案位置、第五冊、單冊101頁、100頁邊界、編譯失敗後舊PDF作廢，以及視覺QA重置等檢查。設定與文件另核對YAML、TOML、參考連結及Python語法。

Windows安裝腳本以PowerShell語法解析與WhatIf檢查控制流程；WhatIf不安裝任何程式。完整乾淨電腦的WinGet/Python/MiKTeX系統安裝屬另一次環境驗收，未執行時不得標成功。中文／數學／TikZ smoke_test會實際呼叫XeLaTeX，有成功PDF仍需看圖才能說版面通過。

## 初版實測紀錄

實測日期：2026-11-13，Windows、Python 3.13.13。

| 項目 | 實際結果 |
|---|---|
| 單元／回歸測試 | 59項獨立測試通過：原有42項、12項任務重用、5項Bash安裝器模擬流程 |
| 官方skill-creator quick_validate | Skill is valid! |
| repo靜態檢查 | Skill YAML、UI欄位、子代理TOML、Python語法與38個相對連結通過 |
| Windows setup | PowerShell AST語法解析及`-WhatIf`預覽通過，預覽不安裝程式 |
| Ubuntu setup.sh | Git Bash `bash -n`語法及`--dry-run`通過；5項模擬測試確認預覽不變更、只查不安裝、skip-system不sudo、apt失敗即停止、未知參數不執行命令 |
| doctor嚴格環境檢查 | 正確回報尚缺PyMuPDF、SymPy、PyYAML及XeLaTeX，沒有把設定副本當成即時載入狀態 |
| 中文／數學／TikZ實際編譯 | 未執行：smoke_test因找不到XeLaTeX明確失敗，未產生PDF通過宣稱 |
| 乾淨Windows完整一鍵安裝 | 未執行；需在目標機器依實際權限安裝並跑smoke_test驗收 |
| 真實Ubuntu apt／TeX／字型安裝及編譯 | 未執行：本機沒有可用Ubuntu／WSL；Git Bash模擬不能替代Ubuntu驗收 |
| 真實全書／子代理／教學／逐頁視覺驗收 | 待使用者提供原書，尚未執行 |
| 省量效果 | 未做真實原書對照，無固定節省比例或5h額度消耗量保證 |

測試檔的PDF、圖片、log及核驗紀錄是明示的合成資料。這些通過結果只檢查程式行為，不證明教材正確或版面完成。真實全書的內容取捨、子代理閱讀完整度、物理／數學正確性、所有冊最終頁數及逐頁視覺檢查，仍需依專案紀錄驗收。執行機器上的驗證專用YAML套件不屬repo依賴安裝成功的證明。

## 編寫 prompt 補強實測

2026-11-14：新增逐章編寫操作規範、完整教學示範及逐章 prompt，重寫全書啟動、來源交接與核驗 prompt。這次重點是實際正文編寫行為，未改動來源處理、封存、分冊與重用程式；上方 59 項為既有版本的回歸紀錄，不冒稱此次重新跑過。

實際以獨立子代理讀取兩頁自造英文來源 S2 並寫成中文章稿，主代理對照來源審閱，查核推導、選法理由、例題、表格、章末提示和完整解答。初稿的公式存放與章號缺漏已回饋、修正並加入正式規範。另以精確分數重算例題／練習及邊界值，檢查入口所有 input 與標籤引用；詳細證據見[試寫入口](../examples/authoring-trial/README.md)及[主代理審閱](../examples/authoring-trial/parent-review.md)。

repo 的 YAML、TOML、Python 語法及相對文件連結、官方 Skill 格式驗證另於打包前重跑。這些檢查和有界寫作試驗都不等於真實原書全書驗收；初次試寫時未執行 XeLaTeX 或 PDF 全頁視覺檢查，後續補驗如下。未測量省量效果。

## Windows 安裝與實際 PDF 補驗

2026-11-14 經使用者授權，使用其下載的基本 MiKTeX 25.12 安裝檔，SHA256 與 Microsoft WinGet 發佈目錄一致；以目前使用者範圍安裝，再更新至 MiKTeX 26.5。首次實測發現既有套件重裝會中止、`tools` 應為 MiKTeX 的 `latex-tools`，以及中文、灰框與交叉引用間接依賴不足；已修正 setup.ps1，明確建格式檔，並讓 MiKTeX 的 smoke_test 停用隱藏的自動補裝對話框，缺項直接回報。

| 本次項目 | 實際結果 |
|---|---|
| Python 與環境 | repo 專用 venv 已安裝全部 requirements，doctor --strict 通過 |
| Windows setup.ps1 | 修正後在已補齊的實機重跑成功，含更新檢查、已安裝套件略過、格式檔建立、兩次 smoke 編譯及 doctor；PowerShell AST 與 WhatIf 亦通過 |
| 共用中文／數學／TikZ 模板 | XeLaTeX 兩次編譯為 1 頁，渲染後目視檢查完成 |
| S2 實際試寫 | 兩次編譯，修正後為 3 頁，全部 3 頁均渲染並目視檢查；沒有缺字、未解析引用、重複標籤或水平／垂直溢出訊息 |
| 字型 | PDF 使用 Microsoft JhengHei Regular／Bold、TeX Gyre Termes 及數學字型；來源頁碼註記取消字型未提供的斜體樣式 |
| 鏡像連線 | 自動鏡像出現 SSL 錯誤，未略過驗證；在該使用者的 MiKTeX 設定中改用實測可連線的 CTAN Illinois HTTPS 鏡像後成功 |

以上是在本機實際安裝、逐項排錯後的整合測試，不能宣稱乾淨 Windows 的完整 WinGet 一鍵流程已從零通過。沒有重新測試 Ubuntu，也沒有真實原書全書、原圖或冊頁數驗收。歷史表格保留初版當時狀態，以本節記錄本次新增證據。

## 新增範本寫法的驗證

2026-11-14：將使用者新提供的 10 張照片逐張歸納為 reference-patterns.md，涵蓋公式鏈、數學補步回原題、模型／圖表比較、完整表與挖空自測、題目梯度及教師語氣。它是寫作參考，不把照片內容或頁碼當原書證據，也不宣稱範本所有科學內容已核。

規則已接入 AGENTS、Skill、全書／逐章編寫、來源閱讀與核驗 prompt；新增 selftestbox 並用於既有 S2 原題。原有三個 math 公式檔及答案內容保留。共用模板 smoke_test（含新自測框）實際兩次編譯為 1 頁；S2 樣稿兩次編譯仍為 3 頁，已渲染並檢查最終各頁。這驗證新框可用及既有樣稿未因更動而破版，不代表所有教學模式已經在真實原書上試寫。

本次另檢查 repo 格式、文件連結與官方 Skill 格式。不重新宣稱歷史 59 項測試或 Ubuntu 安裝已再次驗證；全書內容品質、原書圖表、比較模式的正確適用及省量效果，仍需正式書籍任務驗收。

同日第二批 3 張照片（累計 13 張）補入 P8–P10 與逐張對照：不同量／分布的定義、公式與空間圖對應、敘述型因果及表格證據。作者、來源交接、核驗入口均已接入。此輪僅改文件，執行 repo 文件連結／設定／語法與官方 Skill 格式檢查；未更動公式、模板或程式行為，因此不把前輪 PDF／單元測試說成這一輪重跑，也不宣稱已核正照片的科學內容。

## 安裝與執行依據

- [Codex子代理與設定繼承](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex設定參考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [WinGet install命令](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
- [MiKTeX套件管理命令](https://docs.miktex.org/manual/miktex-packages.html)
- [Microsoft WinGet MiKTeX套件目錄](https://github.com/microsoft/winget-pkgs/tree/master/manifests/m/MiKTeX/MiKTeX)
- [Microsoft WinGet Python3.13套件目錄](https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/Python/Python/3/13)

## 詳細程度標準與前向試寫補驗

2026-11-14，使用者補充完整 84 頁講義，並明確要求成品的核心解釋比範例更詳細。本輪將可操作標準集中於 `skills/textbook-to-zh-tw-notes/references/chapter-authoring.md`，同步作者、來源交接與核驗入口；範例本身及私人路徑未收入 repo。這是解釋深度要求，不是字數、頁數倍數或來源外擴寫。

另由獨立代理只讀更新後的規範及既有兩頁合成來源 S2，實際寫出 `examples/authoring-trial/detailed/` 的正文、章末答案與公式。未照抄既有三頁試寫。初稿漏完整習題題面，另有兩處溫差單位作用範圍不清；均已退修，並由另一位代理對照來源、當前檔案及原有稿件獨立複核。新增說明涵蓋條件使用點、積分常數、單位與方向、端點核對及逐問解題；未增加其他傳熱模型、題目或圖。

| 本輪檢查 | 實際結果 |
|---|---|
| repo 靜態檢查 | `python -X utf8 -B scripts/validate_repo.py` 退出碼 0；YAML、TOML、Python 語法及 99 個相對連結通過 |
| 官方 Skill 格式驗證 | 以宿主的 skill-creator `quick_validate.py` 檢查更新後 Skill，退出碼 0，回報 `Skill is valid!` |
| 數值、符號與來源對照 | Python Fraction 精確運算通過；溫度端點為 30、20°C，中點 25°C；例題為 400 W/m²、200 W；厚度加倍習題為 200 W/m²、100 W，比值 1/2；方向與量綱一致 |
| 獨立內容審閱 | 修正後未發現可操作問題；確認完整例題／習題、來源條件與限制、表格為模型計算值，以及 AI 補步／解答標記 |
| Windows XeLaTeX | 使用停用自動安裝及 shell escape 的命令共執行四次；最後兩次穩定編譯退出碼均為 0，產出 5 頁 A4 PDF |
| PDF 逐頁視覺檢查 | 5 頁全部渲染，試寫代理及主代理均檢視；未見裁切或重疊，公式、表格、灰框、自測與章末答案可讀 |
| 編譯訊息 | 無未定義引用、缺字或 overfull 訊息；學習目標表有一處 underfull hbox，實際頁面換行可讀。引擎另有本機 log 寫入權限及更新狀態提示，未阻止 PDF 產生 |
| 正式收錄檔案一致性 | 七個 TeX／math 檔的 SHA-256 與受審、已編譯試寫逐位元相符；僅收錄可編輯來源，不收錄本機 log、頁圖或環境路徑 |

原有三頁版、早期 59 項測試及後續補驗紀錄均保留各自的版本與範圍。本輪未更動生產程式或重跑其單元測試，不把歷史結果充作本輪重跑；也未驗收真實原書全書、掃描／原圖處理、2–4 冊實際頁限、Ubuntu 系統安裝或用量效果。先前程式驗收缺口不因這份有界試寫而視為已修正。

同日依頁首註解修訂：共用模板及兩份試寫入口預設頁首留白，不印通用標語或空頁首橫線；需要頁首時只使用當前單元名稱。詳細版重新編譯兩次，退出碼均為 0，仍為 5 頁；主代理重看全部頁面，確認頁首留白、頁碼保留且無裁切／重疊。另逐頁比較抽取文字，除移除的固定頁首外，正文文字一致；公式與解答檔未修改。

同日依補充框註解修訂：兩個積分常數原本計算正確，但灰框停在引出結果的冒號，結果式位於框外。現已在框內明寫常數代回的中間式，再 input 同一權威溫度分布式，完成局部推導；並明示結果原已見於 S2。主代理以 SymPy 解兩個邊界方程，確認常數、代回結果、兩端溫度與二階導數均一致；重新編譯兩次退出碼均為 0，仍為 5 頁。全部頁面重新渲染並檢視，補充框的結果與說明完整、沒有裁切／重疊；頁首仍留白、頁碼保留。

## 編譯因果與實際輸入修補

2026-11-14：修補前先凍結版本，實跑原有 54 項單元測試，全部通過；另重現兩個通過既有測試仍存在的缺口：變更版面後，prepare-review 可接受未重新編譯的舊 PDF；inventory 的正文及公式檔也可未進入任何冊的實際編譯。這說明原有測試通過不能代表這兩個關卡正確。

本輪新增共用 XeLaTeX 編譯收據與實際 recorder 輸入檢查，接入全書及單章入口。每次正式編譯使用全新暫存目錄，至少兩輪收斂；每輪 PDF／log／FLS 均須新產生。失敗或逾時使最新收據失效，prepare-review 不能將既有舊產物升格為成功。實際讀入的章稿、答案、inventory output refs、其他專案依賴及允許的外部 TeX／字型資源都有雜湊；註解或條件略過的檔案不算讀入。MiKTeX 的 FLS 不一定列 PDF 為 OUTPUT，因此以新產生的暫存 PDF、引擎 log 的輸出紀錄及 FLS 中的 log OUTPUT 共同核對。

同時將寫作與語意核驗改為逐節交接，可與下一節寫作及獨立目錄的草稿排版並行。未變稿件及依賴沿用有效核驗；本機雜湊及 FLS 檢查不需要將全文重新送入模型。正式成功編譯仍須 teaching 與內容鎖通過，最終 PDF 仍須逐頁視覺 QA。這是流程設計，尚未量測真實書籍的 tokens 節省比例。

獨立 code reviewer 已對照修補前快照審閱實際程式、測試及相關文件，未發現可重現的兩項 P1 修補回歸；該角色未執行測試或 XeLaTeX，動態驗收由另一位獨立 test runner 負責。

| 本輪獨立驗收 | 實際結果 |
|---|---|
| 新增整合驗收 | `python -X utf8 -B -m unittest discover -s skills/textbook-to-zh-tw-notes/tests -p test_p1_independent.py -v`：7 項通過，含真實引擎測試；其餘故障情境使用明示的合成／模擬資料 |
| 完整 Skill 測試 | `python -X utf8 -B -m unittest discover -s skills/textbook-to-zh-tw-notes/tests -p 'test_*.py' -v`：72 項通過，退出碼 0；不計入未重跑的安裝器測試 |
| 真實 Windows XeLaTeX | 合成單章 2 頁、雙冊各 3 頁，均產生兩輪成功收據；核對含空格路徑、首輪未解析引用在後續收斂、各冊章稿／答案、遞迴公式及作者放在 build/ 的輸入；條件／註解略過的檔案未列入實際輸入 |
| 收據與拒絕路徑 | 驗證舊紀錄無法重綁、模擬逾時使成功失效、未編譯 output ref 被拒絕、依賴改動後收據失效，以及多冊專案的舊單 PDF 入口與輸出路徑保護 |
| repo 靜態檢查 | `python -X utf8 -B scripts/validate_repo.py`：退出碼 0，Skill YAML、Codex TOML、Python 語法及 100 個相對連結通過 |

以上實編為合成工程的機械整合驗收，沒有把合成 QA 紀錄或成功收據當作真實教材內容與版面品質已通過。實機測試使用 `STUDYBYMYSELF_TEST_XELATEX` 選擇引擎，或由本機探索；新測試未硬編碼使用者路徑。測試輸出、實編工程及收據留在執行環境的 work/p1-independent，未收入分享檔案。

舊專案需用支援的 compile 入口重新產生收據並重新做最終 PDF 視覺審查；未變且已有有效教學核驗的內容可保留。收據只檢查本機檔案與紀錄的一致性，不是防止所有紀錄遭同時改寫的加密簽章，也不證明來源語意、數學或版面正確。完整目錄／來源單位對帳、頁面預覽與最終 PDF 的逐頁雜湊綁定及可重現打包，仍屬另待改善範圍；本輪也未新增真實原書全書或 Ubuntu 安裝驗收。

## 完整目錄與最終頁圖綁定補驗

2026-11-14：針對上一節列出的目錄對帳及頁圖綁定缺口另行修補。先凍結前一輪已同步版本，以合成雙冊 fixture 重現：原 release 無錯誤；把受審預覽 PNG 換成無關的非圖片檔案，release 仍無錯誤；把兩章都分配至第一個來源單位、使第二個單位未歸入任何章，validate_plan 也無錯誤。舊專案沒有獨立的預期 TOC 總帳，不能只用 chapters_complete 判斷漏章。

全書新增 toc.json，記錄原檔 SHA、核定狀態、預期章節及可回查的目錄／章界證據。book.chapters 以 toc_ids 對應預期章節，每個預期章節必須恰好認領一次；章的來源單位必須等於所對應 TOC 單位的聯集。相鄰章界可以共頁；非章節排除必須有理由與證據，且不能和章節單位重疊。全書的 source.units 亦須覆蓋原 PDF 的全部實際頁面；單章專案仍可處理局部範圍。TOC 及其引用的證據檔加入內容鎖。這是對人工已核目錄總帳的機械對帳，不能自動證明 TOC 轉錄沒有語意遺漏。

單章及全書的 prepare 入口會從成功編譯收據所綁定的 PDF，以 PyMuPDF 自動產生逐頁 PNG 及 manifest，記錄 PDF／收據指紋、頁數、渲染參數、頁碼／路徑／影像雜湊；渲染前後確認 PDF 與收據未變。manifest 納入審閱指紋，每頁觀察須指向對應影像。release 核對全部頁碼、影像與 manifest 指紋，不重新渲染整冊；重新 prepare 會清空舊觀察與通過狀態。普通 draft render 不產生正式 QA 證據。

舊單章專案若已有有效成功編譯收據，重新 prepare 即可產生新的受審頁圖；舊全書專案先核對補齊 TOC 及證據，保留仍有效的來源／內容核驗，依既有流程保存舊鎖、重鎖並正式重編後，再 prepare 及逐頁視覺檢查。不必因新增機械對帳而重讀未變的教材。仍不能把真實渲染、雜湊一致或合成測試紀錄當作來源語意與實際視覺品質已通過；可重現打包、真實原書全書及 Ubuntu 實機驗收未在這次範圍內。

| 本輪驗收 | 實際結果 |
|---|---|
| 新增獨立整合測試 | `python -X utf8 -B -m unittest discover -s skills/textbook-to-zh-tw-notes/tests -p test_coverage_preview_independent.py -v`：8/8，退出碼 0；TOC 共享章界／有證據排除、缺漏／重複／未知映射、實際原 PDF 頁數、證據漂移、單章及雙冊 prepare→manifest→觀察紀錄→release、影像／頁碼互換、manifest／PDF 變更與編譯失敗失效均有覆蓋 |
| 完整 Skill 回歸 | `python -X utf8 -B -m unittest discover -s skills/textbook-to-zh-tw-notes/tests -v`：92/92，退出碼 0，49.682 秒；包含既有真實 MiKTeX 單章與雙冊編譯案例，未另外重跑完整編譯矩陣 |
| 真實渲染證據 | 獨立案例用實際生成的多頁合成 PDF，核對不同頁的文字、PNG SHA-256 及像素資料均不同，未以固定圖片充作所有頁面 |
| 跨版本遷移 | 主代理用凍結前版產生有效單章鎖與收據，再呼叫新版 prepare；原 release 無錯誤，新版退出碼 0、輸出為純 JSON，保留舊鎖與成功收據即可生成新 manifest。開發回歸另核對收據雜湊未改 |
| 獨立程式審閱 | 審閱實際變動、補修及新增獨立測試後，無剩餘可操作問題；確認正式產物寫入邊界、草稿輸出 symlink 拒絕、舊單章 snapshot 相容及單章／全書命令區分。此角色未自行執行測試 |
| repo 靜態檢查 | `python -X utf8 -B scripts/validate_repo.py`：退出碼 0，Skill YAML、Codex TOML、Python 語法與 100 個相對連結通過 |
| 額外頂層安裝器測試 | `python -X utf8 -B -m unittest discover -s tests -v`：退出碼 0，5 項全部因 Bash 不可用而跳過；不計入 92 項通過數，也不作本輪安裝驗收 |

測試與合成工件保存在執行環境的 work/coverage-preview-independent，不收入分享檔案。來源與觀察紀錄明標合成；這些測試只證明程式的對帳與綁定行為，沒有宣稱真實教材語意或視覺品質通過。草稿符號連結拒絕案例在無建立連結權限的宿主使用受控 mock 覆蓋保護分支，不聲稱驗收所有 Windows 權限模式。

## 2026-11-15：OpenCode入口與公式核驗

- repo驗證器通過Skill／OpenCode入口、未變更的Codex設定、Python語法及155個相對連結；官方skill-creator quick_validate以Python UTF-8模式執行通過。
- 完整Skill回歸108項通過，包含原有真實MiKTeX單章／雙冊編譯。Windows深層原路徑觸及MAX_PATH時，以較短工作區副本、相同最終腳本與測試重跑；不是略過該編譯測試。
- 其中公式ledger單元測試11項，以及teaching／snapshot整合測試，確認漏項、同作者審核、缺證據、來源／公式／證據變動、未解項目、非法路徑及不適用理由等行為。
- 最終PDF文字掃描3項測試通過，使用實際PDF文字層；對使用者兩冊vol的唯讀掃描抓到已觀察的候選訂正、占位及內部交接（vol-01共16項、vol-02共10項），每項仍需實際頁面判讀，不能當公式錯誤數量。
- 既有安裝器模擬測試5項通過：在隔離sandbox內Git Bash無法建立signal pipe，改於獲准的本機測試環境重跑成功；未實際安裝系統套件。
- 自造Rindler成稿獨立符號計算5項通過，包含故意錯式的反例：漏平方、錯把座標時間當固有時；同時示範只在ρ=1抽一點會漏掉錯誤。這些計算驗本例，不證明其他教材公式。
- 在本機OpenCode 1.19.5、隔離設定與快取下執行debug skill --pure，成功發現.opencode/skills/textbook-to-zh-tw-notes/SKILL.md並導向權威Skill；未呼叫模型或更改使用者供應商設定。更新repo後需重新啟動OpenCode載入設定。
- 尚未使用Muse Spark實機製作整本原書、未對六份參考PDF逐式審計，也未重新交付六冊PDF。教學觀察範圍見品質基準；不能把上述測試解讀為與Codex品質等同或公式零錯保證。

重現新增的局部檢查：

```text
python examples/codex-style/verify.py
python -m unittest discover -s skills/textbook-to-zh-tw-notes/tests -p test_math_audit.py -v
python -m unittest discover -s skills/textbook-to-zh-tw-notes/tests -p test_pdf_text_audit.py -v
opencode debug skill --pure
```

OpenCode版本不同時先查官方文件及本機help，不能假設debug介面固定。math-audit及內容鎖只驗證紀錄／檔案版本，無法證明實際閱讀、獨立任務或物理正確性。PDF文字掃描為輔助工具，不是release自動判真關卡；原有逐頁視檢仍完整保留。
