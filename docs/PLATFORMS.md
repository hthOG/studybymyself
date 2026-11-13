# Windows、Ubuntu與其他環境

教材規範、Python檢查器及LaTeX模板跨平台；安裝器依作業系統分流。首次安裝前先準備可用的Codex宿主／CLI與帳號登入，本repo不保存或搬移登入資料。Ubuntu可使用Codex CLI／實際提供子代理能力的宿主，不要求Windows桌面版。

| 平台 | 準備命令 | Python入口 | TeX／字型 |
|---|---|---|---|
| Windows | `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1` | `.venv\Scripts\python.exe` | 現有XeLaTeX或MiKTeX；Microsoft JhengHei／Noto TC |
| Ubuntu24.04+ | `bash setup.sh` | `.venv/bin/python` | apt的TeX Live；Noto Serif CJK TC／Noto Sans CJK TC |
| 其他Linux／macOS | 手動備妥依賴；apt系統可評估`bash setup.sh --skip-system` | 專案venv的python | XeLaTeX與模板所需套件、TeX Gyre Termes及Noto CJK TC |

## Ubuntu一鍵準備

```bash
git clone https://github.com/hthOG/studybymyself.git
cd studybymyself
bash setup.sh --dry-run
bash setup.sh
.venv/bin/python scripts/doctor.py --strict
```

腳本只在缺套件時執行apt；安裝Python／venv、TeX Live中文與數學繪圖套件、Noto CJK及TeX Gyre字型。需要管理權限的apt步驟使用sudo；repo venv與pip以目前使用者執行。建議以一般使用者呼叫，不要整支sudo執行。禁止為省事改系統Python、使用sudo pip、繞過宿主權限或自動接受被拒絕的權限。

Ubuntu24.04預設Python滿足本repo的3.11+要求；Ubuntu22.04預設Python3.10不足。22.04若已由管理者備妥Python3.11+及對應venv，可用`bash setup.sh --python python3.12`指定；腳本不偷偷加入第三方PPA或改系統python連結。apt套件在universe時須有對應官方來源；缺來源、離線、無sudo則回報具體步驟，改由管理者準備或使用`--skip-system`，不得假報成功。

`--check-only`只執行doctor，不裝系統套件或Python依賴；`--dry-run`只列計畫；`--skip-system`不執行apt／sudo，仍建立venv、安裝requirements及實際smoke編譯。pip受網路／平台wheel影響可能失敗，保留錯誤即可。

## 平台路徑及搬移

資料契約內部一律使用相對專案根的`/`路徑，例如`content/math/ch01-EQ001.tex`；原書路徑才使用該機器的絕對路徑。Ubuntu區分檔名大小寫；不要使用Windows反斜線、磁碟代號、大小寫不一致的TeX input。命令中的路徑有空白就加引號，Python／TeX用參數陣列呼叫，不把路徑拼成shell指令。

每台機器重新建立`.venv`，不要複製Windows的Scripts到Ubuntu。搬移既有書籍專案時，先把原檔及專案複製到目標機器，更新source.json.path，再核對原書SHA；原檔不變時可重用有效閱讀任務，但來源JSON改動會使舊內容鎖失效，需記搬移原因、重建鎖並在新TeX／字型環境重編各冊、重新逐頁視覺QA。不要把Windows PDF審查宣告直接移作Linux編譯結果。

`.codex/config.toml`的共享子代理設定可沿用，但是否載入及模型可用性仍依各機器Codex版本、信任／管理政策與帳號；不覆寫全域設定。其他作業系統可依規範手動準備後執行doctor與smoke，不能聲稱已有經測試的一鍵安裝支援。

## 驗證邊界

完整Ubuntu安裝驗收應在真實Ubuntu環境執行setup、doctor、59項回歸測試及smoke，再看PDF。Bash語法／模擬流程測試不能證明apt、網路、套件或實際中文字型可用。此次實際測試狀態見[VALIDATION.md](VALIDATION.md)。

依據：[Ubuntu24.04 Python3](https://packages.ubuntu.com/noble/python3)、[venv](https://packages.ubuntu.com/noble/python3-venv)、[XeTeX](https://packages.ubuntu.com/noble/texlive-xetex)、[中文TeX](https://packages.ubuntu.com/noble/texlive-lang-chinese)、[Noto CJK](https://packages.ubuntu.com/noble/fonts-noto-cjk)、[TeX Gyre字型](https://packages.ubuntu.com/noble/fonts-texgyre)。
