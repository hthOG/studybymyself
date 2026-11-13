# 驗證範圍與重現方式

本文件區分程式／規範檢查與實際原書教學驗收。機器測試使用合成PDF與追蹤資料，不能證明有人看過圖、推導成立或中文講義可自學。

## 可重現命令

```powershell
.\.venv\Scripts\python.exe scripts\validate_repo.py
.\.venv\Scripts\python.exe -m unittest discover -s skills\textbook-to-zh-tw-notes\tests -v
.\setup.ps1 -WhatIf
.\setup.ps1 -CheckOnly
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

包含來源抽字不等於已讀、缺頁／缺圖／未核來源、引用落點、公式／來源證據／全書規劃鎖、不同冊的答案位置、第五冊、單冊101頁、100頁邊界、編譯失敗後舊PDF作廢，以及視覺QA重置等檢查。設定與文件另核對YAML、TOML、參考連結及Python語法。

Windows安裝腳本以PowerShell語法解析與WhatIf檢查控制流程；WhatIf不安裝任何程式。完整乾淨電腦的WinGet/Python/MiKTeX系統安裝屬另一次環境驗收，未執行時不得標成功。中文／數學／TikZ smoke_test會實際呼叫XeLaTeX，有成功PDF仍需看圖才能說版面通過。

## 初版實測紀錄

實測日期：2026-11-13，Windows、Python 3.13.13。

| 項目 | 實際結果 |
|---|---|
| 單元／回歸測試 | 42項獨立測試通過（27項來源／鎖／單PDF，15項全書分冊） |
| 官方skill-creator quick_validate | Skill is valid! |
| repo靜態檢查 | Skill YAML、UI欄位、子代理TOML、Python語法與29個相對連結通過 |
| Windows setup | PowerShell AST語法解析及`-WhatIf`預覽通過，預覽不安裝程式 |
| doctor嚴格環境檢查 | 正確回報尚缺PyMuPDF、SymPy、PyYAML及XeLaTeX，沒有把設定副本當成即時載入狀態 |
| 中文／數學／TikZ實際編譯 | 未執行：smoke_test因找不到XeLaTeX明確失敗，未產生PDF通過宣稱 |
| 乾淨Windows完整一鍵安裝 | 未執行；需在目標機器依實際權限安裝並跑smoke_test驗收 |
| 真實全書／子代理／教學／逐頁視覺驗收 | 待使用者提供原書，尚未執行 |

測試檔的PDF、圖片、log及核驗紀錄是明示的合成資料。這些通過結果只檢查程式行為，不證明教材正確或版面完成。真實全書的內容取捨、子代理閱讀完整度、物理／數學正確性、所有冊最終頁數及逐頁視覺檢查，仍需依專案紀錄驗收。執行機器上的驗證專用YAML套件不屬repo依賴安裝成功的證明。

## 安裝與執行依據

- [Codex子代理與設定繼承](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex設定參考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [WinGet install命令](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
- [MiKTeX套件管理命令](https://docs.miktex.org/manual/miktex-packages.html)
- [Microsoft WinGet MiKTeX套件目錄](https://github.com/microsoft/winget-pkgs/tree/master/manifests/m/MiKTeX/MiKTeX)
- [Microsoft WinGet Python3.13套件目錄](https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/Python/Python/3/13)
