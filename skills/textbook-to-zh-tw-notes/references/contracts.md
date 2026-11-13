> 全書模式的分工、內容取捨與多冊驗收以[全書契約](book-contract.md)及[協作契約](agent-workflow.md)為準。本檔保留單專案來源／內容資料格式，單PDF release只適用單章工具；整本書必須用book.py check。

# 階段交接、資料格式與關卡

## 目錄與權威來源

```text
chapter-project/
  source.json                 原檔身分、範圍、來源單位及雙頁碼
  source/text/u0001.txt        逐頁抽字／覆核後 OCR；不能覆蓋原書
  source/previews/             原頁圖或 EPUB 區段截圖
  coverage.json               逐來源單位的閱讀證據
  inventory.json              原書物件 → 講義位置的對照
  progress.json               目前階段、小節續點、未解事項
  content/outline.md          目標、概念依賴、來源對照與題目計畫
  content/chapter.tex         講義主體，含術語／符號與來源對照
  content/answers.tex         獨立題的提示、解答
  content/math/EQ001.tex      重要公式／逐段推導，正文 input 引入
  content/figures/            裁圖／重繪圖與可編輯圖源
  verification.md            推導與逐題的實際核驗證據
  qa.json                    七項要求、來源及圖表語意核驗、PDF QA
  content-lock.json           內容樹雜湊，排版前建立
  layout/main.tex             外觀、字體、版面；只引用 content
  build/                      PDF、log、編譯命令及逐頁 PDF 預覽
  quality-report.md          人可讀的結果、略過項目與限制
```

`content/*.tex` 是正式教學內容的單一權威，`outline.md` 只規劃，不另寫一份會與 LaTeX 漂移的正式 Markdown。需要 Markdown 版本時可額外產生，但必須由已核驗內容轉出並核對公式。原書不能放入對外分享的專案 ZIP，除非使用者另有要求；一般只附其雜湊、書目與對照。

所有檔案 UTF-8。JSON 的路徑一律相對專案根，不得逃出專案；`source.json.path` 是唯讀原檔的絕對路徑，屬例外。ID 建立後穩定，改章界時保留變更紀錄而非靜默刪除項目。

## source.json 與 coverage.json

PDF `init` 會自動建立下列資料；腳本不自動判斷章界與閱讀完成。書目、印刷頁碼、scope_note 需實際核對後補寫。

```json
{
  "schema_version": 1,
  "source_id": "B1",
  "path": "C:/books/book.pdf",
  "sha256": "原檔的64位十六進位雜湊",
  "kind": "pdf",
  "bibliography": {"title": null, "authors": null, "edition": null, "year": null},
  "scope": "第7章；含章末題目，不含下一章",
  "scope_verified": false,
  "units": [
    {"id": "u0001", "pdf_page": 174, "printed_page": "158",
     "anchor": null, "section": "7.2", "scope_note": "整頁",
     "text_path": "source/text/u0001.txt", "preview_path": "source/previews/u0001.png"}
  ]
}
```

EPUB 手動建相同結構，`kind=epub`，各 unit 的 `pdf_page=null`、`printed_page=null`、`anchor` 為唯一穩定定位，例如 `chapter7.xhtml#sec2`。每個來源區段都保存可再次讀的文字與頁面／區段預覽。紙本拍照掃描可先組成 PDF，再逐頁建檔；不能把估算頁碼當已核對頁碼。

```json
{
  "units": [
    {"id": "u0001", "text_review": "pending", "visual_review": "pending",
     "evidence": "", "issues": []}
  ]
}
```

完成後兩個 review 填 `done`，`evidence` 具體記錄本頁辨識出的內容與原頁核對處。僅「已看」不足以支持閱讀。真正無文字的來源單位可用 `text_review=not_applicable`，並在 evidence 解釋。欄位是操作者紀錄，機器不能證明真讀過。

## inventory.json

先逐原頁建立，寫作後才填落點。`complete=true` 只能在回看原頁確認清單沒有漏項後填。PDF 每個項目的 locator 使用 source unit ID；精確章節／原式／圖／題號保存在 `locator`。

```json
{
  "complete": false,
  "items": [
    {"id": "E7-6", "category": "equation", "title": "動能定理",
     "units": ["u0001"], "locator": "第7章 §7.2，式(7.6)",
     "locator_verified": false, "disposition": "pending", "reason": "",
     "omission_basis": null, "user_scope_evidence": "",
     "output_refs": [{"file": "content/chapter.tex", "anchor": "\\label{src-E7-6}"}],
     "verification_ref": {"file": "verification.md", "anchor": "E7-6"}}
  ]
}
```

category：`section/concept/equation/derivation/example/figure/table/exercise`。全書物件另有`priority=A/B/C`及`priority_reason`。完整閱讀後才能判斷是否不存在某類物件，不為了填表虛構原式／原圖。正文每小節至少有 section 項；其他各類按原書實際內容建清單。

`output_refs` 是實際檔案與可搜尋的唯一標記（通常為 LaTeX label）；不能指向空檔或只有待寫標題。重要推導的來源頁碼也要直接印在正文，不只藏於 JSON。機器只檢查標記是否存在，不理解內容是否足夠。

`covered`或`compressed`必須有來源定位、locator_verified與落點；compressed另需reason。`equation/derivation/example/figure/table/exercise` 另有 `verification_ref` 指向真實核驗紀錄：公式逐式核對，題目逐題驗算，圖表逐項比圖。合併解說時多個來源項目可指向同一段，但須有完整對照。

`omitted` 必須有 reason 及 omission_basis：`decorative` 僅可用於裝飾圖，`exercise_selection` 僅可用於未選取的章末題庫，`user_scope` 需在 user_scope_evidence 記具體使用者授權。所有略過項目要印在品質報告；必需內容不能因「篇幅有限」而默默略過。全書模式另允許B/C級因篇幅取捨用`omission_basis=editorial_budget`，必須具體記理由，不能省略A級。未核實的項目維持pending。

## qa.json

```json
{
  "requirements": {
    "concepts": {"status": "pending", "evidence": []},
    "derivations": {"status": "pending", "evidence": []},
    "deep_analysis": {"status": "pending", "evidence": []},
    "examples": {"status": "pending", "evidence": []},
    "figures_tables": {"status": "pending", "evidence": []},
    "bilingual_terms": {"status": "pending", "evidence": []},
    "review_exercises_answers": {"status": "pending", "evidence": []}
  },
  "semantic_review": {"status": "pending", "evidence": []},
  "pdf": {"status": "pending", "path": "build/main.pdf", "log": "build/main.log",
    "build_record": "build/compile.txt", "page_count": 0, "reviewed_pages": [], "issues": []},
  "unresolved": []
}
```

每個 evidence 項是 `{"file":"content/chapter.tex","anchor":"\\label{某實際標記}"}`；也可指向 verification.md 的詳細審查紀錄。semantic_review 記原文回查、AI 標籤、引用語意及圖表解讀核驗。全部完成後 status 改 pass。

PDF reviewed_pages 的每項為 `{"page":1,"preview":"build/previews/page-1.png","notes":"實際檢查內容"}`；實際看過才可登記。其 page_count 以實際 PDF 確認；log 是最後編譯 log，compile.txt 保存命令、時間、結果及 warning 處理。所有 PDF 頁都需覆蓋，不以首尾抽樣代替。

本次成功編譯後先執行 `prepare-pdf-review`，由實際 PDF 填 page_count，保存 `review_fingerprint`，清空先前逐頁紀錄。此指紋含 PDF／log／編譯紀錄／版面／內容鎖，變更後要重編譯並重做相應視覺檢查。指紋只保證審查對象沒變，不能證明編譯的因果關係，compile.txt 必須忠實記錄本次成功編譯。pypdf 是 init、prepare-pdf-review 及 release 讀取 PDF 所需依賴，其餘結構檢查使用 Python 標準函式庫。

## 關卡與續作

- source 關卡：原檔雜湊正確、範圍核實、全部來源單位的讀字／看圖紀錄與證據檔齊、無未解來源問題、清單完整且定位核實。這時來源清單可以仍是 pending。
- teaching 關卡：source 條件，加上所有項目已 covered、合規 compressed 或合法列明略過、七項成果及語意檢查有證據、無未解內容問題、章稿／答案／核驗紀錄存在。
- lock：只有 teaching 通過才建立 content 樹的逐檔 SHA-256，以及 source/coverage/inventory/verification 的當時雜湊。鎖檔不能自動覆蓋；修內容時先另存舊鎖，記修正原因、完成受影響內容核驗，再執行 lock。
- release 關卡：teaching 條件，加上來源證據與 content 沒變、PDF／log／編譯紀錄存在、PDF 的實際頁數與逐頁視覺紀錄一致、無未解 PDF 問題、quality-report.md 完成。

`progress.json` 至少保存 `stage/next_section/open_issues`；每個小節與每次回退立即更新。來源換版 → 來源核對；推導／題面／圖義改動 → 內容核驗；只改字體／寬度 → 重編譯及 PDF QA。先前通過的狀態不能無條件繼承。

靜態腳本是檢查紀錄與檔案的工具，不是內容裁判。不得為了通過檢查偽造 evidence、刪掉來源項目、把 pending 改 omitted，或寫入未實際執行的測試結果。
