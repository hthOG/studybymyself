# 全書規劃、分冊與頁數契約

## 專案結構

全書使用單一來源／覆蓋總帳與內容鎖，避免各章互相覆寫。`book.py init` 建立待填結構；主代理及子代理依[協作契約](agent-workflow.md)工作。

```text
book-project/
  source.json / source/text/ / source/previews/   全書逐頁來源，主代理不全文讀取
  coverage.json / inventory.json                主代理合併的權威總帳
  toc.json                                      原書完整章目、來源PDF雜湊與章／排除頁對帳
  book.json                                     全書章節、分冊、預算與各冊QA
  progress.json                                 任務波次、續點與effort紀錄
  tasks/<task-id>/                               子代理的限定寫入區
  content/outline.md                            全書依賴、A/B/C級與頁數規劃
  content/chapter.tex                           正文檔案索引，不含整書原文
  content/answers.tex                           答案檔案索引
  content/chapters/ch01.tex                      章稿
  content/answers/ch01.tex                       該章提示與答案
  content/math/ch01-EQ001.tex                    單一權威公式
  content/figures/                              原圖優先；必要重繪附來源
  selection-log.md / verification.md            選題／壓縮／略過、核驗與訂正
  layout/vol-01.tex ...                          各冊獨立入口與字體／版面
  content-lock.json                             內容與教學證據鎖
  build/vol-01.pdf/.log/.compile.txt/.compile.fls 成功編譯證據與實際輸入軌跡
  build/.latex-vol-01-<unique>/                  本次編譯的隔離暫存輸出
  build/previews/<run-id>/                       最終PDF逐頁PNG及manifest.json
  quality-report.md                             全書＋逐冊品質報告
```

## book.json

```json
{
  "schema_version": 1,
  "chapters_complete": false,
  "chapters": [
    {"id": "ch01", "title": "原書第1章", "toc_ids": ["toc-001"], "units": ["u0015", "u0016"],
     "treatment": "full", "priority_reason": "後續各章的基礎",
     "output": "content/chapters/ch01.tex", "answers": "content/answers/ch01.tex"}
  ],
  "volumes": [
    {"id": "vol-01", "chapter_ids": ["ch01"], "planned_pages": 85,
     "layout": "layout/vol-01.tex",
     "qa": {"status": "pending", "path": "build/vol-01.pdf", "log": "build/vol-01.log",
       "build_record": "build/vol-01.compile.txt", "page_count": 0, "preview_manifest": null,
       "reviewed_pages": [], "issues": []}}
  ]
}
```

`chapters_complete` 必須在根據完整目錄核對所有章節後才設true。每章有穩定ID、來源units、標題及priority_reason。treatment為full/compressed/omitted；compressed／omitted須給reason，並在selection-log記原因與影響。被省略的章仍要完成來源閱讀、來源物件清單與省略記錄，不能從章節表刪除。保留／壓縮的每章恰好歸入一冊，省略章不歸冊。相鄰章可共用來源頁（章界共頁）；以scope_note精確區分。

`toc.json` 是人工核對原書目錄後的權威預期章表，不是由 `chapters_complete` 推論而來。`book.py init` 先建 pending 結構；核對後填入 `source_sha256`（必須等於 `source.json` 中原始PDF SHA-256）、root/chapter/exclusion 的 `evidence`（每項至少含原書單位 `text_path` 或 `preview_path` 及可回查的 `{file, anchor}`）、`chapters` 與 `exclusions`，最後標記 `status: "verified"`。每個 TOC chapter 含穩定 `id`、標題、原書定位及來源 `units`。每個 `book.chapters` 項用一個或多個 `toc_ids` 對應預期章；每個 TOC id 恰好出現一次，該章 `units` 必須等於其 TOC units 聯集。所有原書PDF物理頁都要有一個 source unit；全部source units必須落在TOC章或明示有理由與證據的 nonchapter exclusions。相鄰章邊界可重疊同一unit；exclusions不可與章重疊。機器只核對已人工確認的帳本與來源範圍，不判斷目錄轉錄有無語意漏項。

最小結構示例（`chapters` 對應原書預期章，並非講義取捨後的清單）：

```json
{
  "schema_version": 1,
  "source_sha256": "原始PDF的64位SHA-256",
  "status": "verified",
  "evidence": [{"file": "source/text/u0001.txt", "anchor": "Contents"}],
  "chapters": [{"id": "toc-001", "title": "Chapter 1", "locator": "PDF p. 4",
    "units": ["u0004", "u0005"],
    "evidence": [{"file": "source/text/u0001.txt", "anchor": "Chapter 1"}]}],
  "exclusions": [{"units": ["u0001"], "reason": "Title page",
    "evidence": [{"file": "source/text/u0001.txt", "anchor": "Title page"}]}]
}
```

每冊planned_pages是估算，須>0且≤100，不是通過頁限的證據。每冊id、layout、PDF路徑唯一。全書規劃2、3或4冊，不為了湊100頁填水；冊間按主題／概念依賴切分，避免只按字數均分。短書仍預設2冊，使用者另要求1冊時才變更規範與檢查設定。

## 篇幅分配

先以目錄與子代理回報估算，選2冊；需要時擴到3冊，只有重要內容很多時擴到4冊。建議每冊先估85–90頁，保留重排與目錄／答案的空間。主代理把每章正文、原圖、例題、章末答案及冊前頁的預算明列，不能漏計解答。

超頁先移除重複敘述與重複圖／題、合併B級說明，再壓縮／略過C級；不可刪掉關鍵推導理由、公式條件、單位或必要圖說。若仍超過4×100頁，按使用者授權保留重要概念、關鍵推導與代表例題，記所有取捨。取捨前仍完整閱讀，以免把沒讀當成不重要。

壓縮可移動章節配置；不可用難讀字體、極窄頁邊、章外隱藏附件或第五冊規避。參考解答不能移出計頁範圍。每冊單獨用PDF實際頁數驗收，不只檢查總數≤400。

## 與舊資料格式的關係

[contracts.md](contracts.md) 定義source/coverage/inventory/qa、逐檔鎖與source/teaching關卡，沿用其機械格式。全書模式以book.py的多冊release取代project.py的單PDF release；qa.json.pdf只是舊單章欄位，不能拿它冒充多冊驗收。

inventory新增`priority`與`priority_reason`，`disposition=compressed`需有output_refs與reason；A級不得omitted。C／B級因頁數取捨omitted時用`omission_basis=editorial_budget`並給reason。這是使用者已授權的有限篇幅取捨；不是任意少讀的理由。正文例題也可選代表性物件，不要求全題照搬；未選題及理由必須進selection-log。

## 編譯與終審

正文及各章答案索引需能回查；每冊入口自己input所屬章及該章答案，不把全書答案重印到每冊。每個章結束後接提示與答案，避免提前洩題。共用模板在layout，正式內容在content；後者先核驗再鎖。

`book.py compile` 先失效所有舊編譯收據與視覺紀錄，再要求teaching檢查及內容鎖一致。每冊在新建隔離暫存目錄執行XeLaTeX `-recorder`，每一輪都必須重新產生PDF、log與`.fls`，至少兩輪且交叉引用、實際輸入及相關輔助檔穩定；拒絕錯誤／缺字／未定義引用、缺少新產物或超頁。輸出通過後才發布到正式PDF／log路徑並建立JSON build receipt（檔名仍用`*.compile.txt`）；receipt記錄本次鎖檔、版面、逐輪結果、PDF／log／recorder指紋及實際輸入清單。失敗或逾時會保存失敗狀態，先前成功不會留存為最新成功。

`book.py prepare-review` 只接受可驗證的成功receipt；驗證後由受支持的本機PyMuPDF renderer直接讀取最終PDF，產生每頁PNG及`manifest.json`，記錄PDF SHA、receipt SHA、頁數、renderer/參數、頁碼到PNG路徑及每圖SHA，清空舊逐頁notes，再固定新的review fingerprint。standalone使用`project.py prepare-pdf-review`走同一路徑。release核對manifest、當前PDF/receipt、頁碼映射及所有PNG雜湊，不重render；任何PDF、receipt、manifest或預覽變更都必須重新prepare並完整逐頁審閱。普通`render.py pdf`僅產生draft圖，不建立正式QA。這些hash不是可抵禦使用者重寫所有ledger的加密簽章。舊專案缺TOC或manifest時會fail closed：補齊並驗證toc.json、保留仍有效的teaching核驗、重鎖後重編正式PDF並prepare新頁圖；不需重讀未變且已有效核驗的原書內容。

release會以`.fls`實際讀入清單確認每章正文與答案索引、以及每個covered/compressed inventory output ref都出現在對應冊的編譯輸入。遞迴`\input`會由XeLaTeX記錄；註解、`iffalse`及`includeonly`略過的檔不算已編譯輸入。專案內所有實際輸入（包括`build/`中的作者檔）都納入雜湊。隔離暫存目錄中只有被`.fls`記錄為compiler `OUTPUT`且副檔名屬編譯輔助檔的輸入才排除出作者清單。外部TeX系統資源與系統字型僅允許位於該引擎可定位的TeX distribution/TEXMF、MiKTeX格式／設定快取或作業系統字型根目錄；其路徑與雜湊也會在prepare/check時重新確認。專案外任意`.tex`或其他未列入系統根的外部依賴須複製進專案。這些hash與recorder驗證追蹤普通檔案變更，不是對可同時改寫所有紀錄者的加密簽章，也不判定來源語意。

編寫期間可在獨立draft目錄編譯，以便提早查看頁面；draft不得寫入正式`build/*.compile.txt`，也不能建立release QA。各節完成後，語意核驗可與後續章節寫作並行；正式證據編譯仍需在accepted teaching與內容鎖完成後進行。

`book.py check`：source/teaching通過、章表與冊配置閉合、2–4冊、每冊實際≤100頁、每冊內容鎖／PDF指紋未變、逐頁視覺記錄齊、沒有未解關鍵問題、selection-log及quality-report存在。頁碼對應、來源語意及推導正確性仍由代理核驗，不能靠JSON欄位自證。

## 任務索引及可續接成果

tasks/index.json由主代理記每個來源／核驗任務的範圍、狀態、交接路徑、收據與依賴；任務收據位於tasks/<id>/reuse-receipt.json。使用量可記usage-log.jsonl，未知值寫null。續作先依[重用規則](efficiency.md)核對有效性，再只處理待補／失效／未完成範圍；這不變更source／teaching／release的必要條件。
