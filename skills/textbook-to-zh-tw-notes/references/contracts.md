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
    "build_record": "build/compile.txt", "recorder": "build/compile.fls",
    "page_count": 0, "preview_manifest": null, "reviewed_pages": [], "issues": []},
  "unresolved": []
}
```

每個 evidence 項是 `{"file":"content/chapter.tex","anchor":"\\label{某實際標記}"}`；也可指向 verification.md 的詳細審查紀錄。semantic_review 記原文回查、AI 標籤、引用語意及圖表解讀核驗。全部完成後 status 改 pass。

PDF reviewed_pages 的每項為 `{"page":1,"preview":"build/previews/<run-id>/page-001.png","notes":"實際檢查內容"}`；實際看過才可登記。其 `preview_manifest` 指向由最終PDF本機render產生的 `manifest.json`；release核對PDF／receipt SHA、頁碼映射、PNG格式與每頁SHA，notes仍由人實際填寫。`render.py pdf`產生的draft圖不建立正式QA。所有PDF頁都需覆蓋，不以首尾抽樣代替。

單章正式流程為 `project.py compile <project>` → `project.py prepare-pdf-review <project>` → 實際逐頁檢查 → `project.py check <project> --stage release`。`compile`必須先有通過teaching的內容鎖，並使用新隔離輸出目錄及XeLaTeX `-recorder`；每一輪都需新產生PDF／log／FLS，至少兩輪且輔助輸出穩定，記錄成功、失敗或逾時狀態。`build/compile.txt`是含結構化JSON的成功receipt，`build/compile.fls`是本次實際輸入軌跡。只有compile可以產生成功receipt。

`prepare-pdf-review`會驗證receipt、鎖檔、版面、所有實際輸入及輸出雜湊後，由受支持的本機PyMuPDF renderer直接從最終PDF產生每頁PNG與manifest，再填page_count、保存manifest／`review_fingerprint`並清空先前逐頁紀錄。manifest記PDF與成功receipt的SHA、頁數、renderer/參數，以及頁碼、PNG路徑與每圖SHA。release以當前PDF／receipt及PNG逐項核對manifest，不重render；改PDF、重編、manifest、預覽圖或頁碼對應都須重新prepare並逐頁審閱。prepare不會由現有PDF／log／任意文字紀錄製造「編譯成功」，也不自動通過視覺QA。舊receipt格式需先真正重編；已有效teaching核驗仍可沿用，不要求重讀全書。`review_fingerprint`偵測審查對象漂移，receipt連結編譯與實際檔案輸入；檔案雜湊不是抵禦同時改寫所有ledger的加密簽章。pypdf是init、compile、prepare及release讀取PDF頁數所需依賴；正式預覽使用PyMuPDF。

FLS的`PWD`與相對／絕對`INPUT`／`OUTPUT`會安全正規化。專案內所有實際輸入都逐檔雜湊，包含作者放在`build/`中的檔案；只有位於本次隔離暫存目錄、且被本次XeLaTeX `OUTPUT`記錄的已知編譯輔助輸入會被排除。專案外輸入必須位於引擎可定位的TeX distribution/TEXMF、MiKTeX格式／設定快取或OS字型根目錄，並保留路徑及雜湊供prepare/release重新確認；任意外部`.tex`需先納入專案。release亦確認`layout/main.tex`、正文／答案及每個covered/compressed output ref真的在FLS輸入清單中；TeX註解或條件略過不能算實際引用。

若專案含`book.json`，`project.py compile`、`prepare-pdf-review`及`check --stage release`都拒絕執行，須改用`book.py compile`、`prepare-review`及`check`。整本書teaching也要求已核TOC ledger；`toc.json`記錄原始PDF SHA、每個預期章節對應來源units及有證據的非章節排除。全部source units須被章節覆蓋或明示排除，章間界頁可重疊；全書source units還必須覆蓋原PDF每個實體頁面。`toc.json`及其root/chapter/exclusion證據檔都納入內容鎖。單PDF路徑不能冒充多冊驗收。

## 關卡與續作

- source 關卡：原檔雜湊正確、範圍核實、全部來源單位的讀字／看圖紀錄與證據檔齊、無未解來源問題、清單完整且定位核實。這時來源清單可以仍是 pending。
- teaching 關卡：source 條件，加上所有項目已 covered、合規 compressed 或合法列明略過、七項成果及語意檢查有證據、無未解內容問題、章稿／答案／核驗紀錄存在。
- lock：只有 teaching 通過才建立 content 樹的逐檔 SHA-256，以及source/coverage/inventory/verification的當時雜湊；全書另鎖`toc.json`、章映射及TOC root/chapter/exclusion evidence引用檔。鎖檔不能自動覆蓋；修內容時先另存舊鎖，記修正原因、完成受影響內容核驗，再執行lock。
- release 關卡：teaching 條件，加上來源證據與 content 沒變、PDF／log／編譯紀錄存在、PDF 的實際頁數與逐頁視覺紀錄一致、無未解 PDF 問題、quality-report.md 完成。

`progress.json` 至少保存 `stage/next_section/open_issues`；每個小節與每次回退立即更新。來源換版 → 來源核對；推導／題面／圖義改動 → 內容核驗；只改字體／寬度 → 重編譯及 PDF QA。先前通過的狀態不能無條件繼承。

靜態腳本是檢查紀錄與檔案的工具，不是內容裁判。不得為了通過檢查偽造 evidence、刪掉來源項目、把 pending 改 omitted，或寫入未實際執行的測試結果。
