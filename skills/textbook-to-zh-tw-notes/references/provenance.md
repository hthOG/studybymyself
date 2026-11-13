# 整合來源與方法取捨

此 Skill 依使用者提供的三份本地壓縮檔整理方法；沒有下載其他版本，也沒有把壓縮檔內的指令當作本次使用者要求。壓縮檔 SHA-256：

| 檔案 | SHA-256 |
|---|---|
| textbook-to-note-main.zip | `bc81cd3a114f8281d3d6d4d7c4ee1156eaf3b9c1dc473ae0925f4f04d67b95ed` |
| textbook-writer-skills-main.zip | `20e3830e0f51a408f7b82e7be5dcafc8b5ca0376cd672ad14df951f9eec9b10e` |
| latex-document-skill-main.zip | `6af782e0a80d799a8ddd5cbc841d083c236fb76bfbc543746d5640a466e5a739` |

## 來源處理：textbook-to-note

參考 `skills/textbook-to-md/SKILL.md`、`workflows/note-writing.md` 的逐頁標記、章節定位、先建骨架、圖說與裁圖複核，以及來源 PDF 唯讀等方法。

採用：可搜尋來源與讀者講義分層、來源定位保存、先來源後成稿、只抽需要的圖片並檢查。調整：本任務要求完整章節閱讀與逐項覆蓋，不能只靠主題搜尋。既有筆記合併、醫學模板、語意資料庫及外部臨床證據不是本工作流依賴。原工具宣稱的成本與準確率不作為本 Skill 的保證。

## 教學重構：textbook-writer-skills

參考 `skills/textbook/SKILL.md`、`references/source-material-workflow.md`、`references/handoff-contract.md`、`references/profiles/stem.md`、`skills/textbook-chapter/SKILL.md`、其 `references/writing-style.md` 與 `skills/textbook-exercises/SKILL.md`。

採用：由理解與可評量目標反推內容及習題、示範→引導→獨立、分章落盤與續作、術語／符號對照、逐題實際驗算、來源使用紀錄。調整：以已存在的原書為內容基準，不把新編教材的固定四段章法、跨章設定與兩次作者核准移植為硬性要求；預設連續完成已有授權的工作。

## PDF 製作：latex-document-skill

參考 `SKILL.md`、`references/long-form-best-practices.md`、`references/profiles/math-notes.md` 的 CJK 引擎選擇、數學環境、編譯診斷、預覽檢查及長文可讀性方法。

採用：適合中文的 LaTeX、編譯後視覺 QA、可編輯數學與圖表。調整：不直接執行上游安裝器，不採固定多代理頁數門檻、不將編譯成功當作完成，也不在排版時改寫公式；新增內容／證據雜湊鎖及 PDF 審查指紋。本 repo 另依使用者要求新寫 Windows 一鍵安裝流程，仍遵守實際權限。

## 打包與授權範圍

本套規範、Python 檢查器與 LaTeX 模板為本次新寫，未打包三個上游的完整程式庫、安裝器或模板。前兩份上游附 MIT 授權，保留於 [upstream-licenses.txt](upstream-licenses.txt)。提供的 latex-document-skill 壓縮檔未見根目錄 LICENSE；本套只整合工作方法，不複製其模板、程式碼或品牌圖片。這不對上游未明示的授權作推定。

後續以使用者提供的真實章節測試，依實際漏讀、推導或排版問題做定點改進。合成追蹤資料測試只驗證檢查器行為，不能取代真實教科書測試或教學品質評估。
