# 全書規劃、分冊與頁數契約

## 專案結構

全書使用單一來源／覆蓋總帳與內容鎖，避免各章互相覆寫。`book.py init` 建立待填結構；主代理及子代理依[協作契約](agent-workflow.md)工作。

```text
book-project/
  source.json / source/text/ / source/previews/   全書逐頁來源，主代理不全文讀取
  coverage.json / inventory.json                主代理合併的權威總帳
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
  build/vol-01.pdf/.log/.compile.txt             成功編譯證據
  build/previews/vol-01/                         逐頁圖像
  quality-report.md                             全書＋逐冊品質報告
```

## book.json

```json
{
  "schema_version": 1,
  "chapters_complete": false,
  "chapters": [
    {"id": "ch01", "title": "原書第1章", "units": ["u0015", "u0016"],
     "treatment": "full", "priority_reason": "後續各章的基礎",
     "output": "content/chapters/ch01.tex", "answers": "content/answers/ch01.tex"}
  ],
  "volumes": [
    {"id": "vol-01", "chapter_ids": ["ch01"], "planned_pages": 85,
     "layout": "layout/vol-01.tex",
     "qa": {"status": "pending", "path": "build/vol-01.pdf", "log": "build/vol-01.log",
       "build_record": "build/vol-01.compile.txt", "page_count": 0, "reviewed_pages": [], "issues": []}}
  ]
}
```

`chapters_complete` 必須在根據完整目錄核對所有章節後才設true。每章有穩定ID、來源units、標題及priority_reason。treatment為full/compressed/omitted；compressed／omitted須給reason，並在selection-log記原因與影響。被省略的章仍要完成來源閱讀、來源物件清單與省略記錄，不能從章節表刪除。保留／壓縮的每章恰好歸入一冊，省略章不歸冊。相鄰章可共用來源頁（章界共頁）；以scope_note精確區分。

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

`book.py compile` 先要求teaching檢查及內容鎖一致，依序執行XeLaTeX至少兩輪，保存命令／退出結果，拒絕殘留未定義引用／缺字，檢查實際頁數。最終輪仍有交叉引用重跑警告則停止要求處理，不把舊PDF當成功。每冊重新編譯後執行`prepare-review`，將全部PDF轉為頁圖；主／子代理實際逐頁看過後寫該冊qa.reviewed_pages。

`book.py check`：source/teaching通過、章表與冊配置閉合、2–4冊、每冊實際≤100頁、每冊內容鎖／PDF指紋未變、逐頁視覺記錄齊、沒有未解關鍵問題、selection-log及quality-report存在。頁碼對應、來源語意及推導正確性仍由代理核驗，不能靠JSON欄位自證。
