# 三同藥品查詢（線上公開版）— 上線步驟

這份文件是給業主（Ron）的操作指南。整個網站只有一個網頁（`index.html`）和一份資料（`data/nhi.json`），
放在 GitHub 上面就能免費公開給大家查詢，之後每個月會自動更新資料。

## 第一次上線（七個步驟）

1. **註冊 / 登入 GitHub**：到 https://github.com 用 Email 註冊一個免費帳號（如果已經有帳號就直接登入）。

2. **建立新的 repository（專案）**：
   - 點右上角「+」→「New repository」
   - Repository name 填 `sansame`
   - 選 **Public**（公開；免費版的 GitHub Pages 需要公開才能用）
   - 不要勾選「Add a README file」
   - 按「Create repository」

3. **把這個資料夾的內容上傳上去**：在這個資料夾（`線上版/`）打開終端機，依序執行：

   ```bash
   git init
   git add .
   git commit -m "初始上線"
   git branch -M main
   git remote add origin https://github.com/<你的帳號>/sansame.git
   git push -u origin main
   ```

   第一次 push 時會要求登入，照畫面指示用瀏覽器授權即可。

4. **把排程檔放到正確位置**：GitHub 只會辨識 `.github/workflows/` 資料夾裡的排程檔，所以要把
   `workflow-放到.github-workflows/update.yml` 搬到 `.github/workflows/update.yml`，再重新 commit 推送：

   ```bash
   mkdir -p .github/workflows
   git mv "workflow-放到.github-workflows/update.yml" .github/workflows/update.yml
   git commit -m "加入自動更新排程"
   git push
   ```

5. **開啟 GitHub Pages**：在 GitHub 網頁上，進入 `sansame` 專案 → **Settings** → 左側選單 **Pages**
   → 「Build and deployment」的 **Source** 選 **GitHub Actions**。

6. **手動執行一次，確認成功**：進入專案的 **Actions** 分頁 → 左側選「更新健保藥品資料並發布網頁」
   → 右邊「Run workflow」→ 按綠色按鈕執行。等待約 1～2 分鐘，確認流程全部打勾（綠色）。

7. **拿到網址**：流程成功後，回到 **Settings → Pages**，上方會顯示網址，格式是：

   ```
   https://<你的帳號>.github.io/sansame/
   ```

   把這個網址分享給其他藥師即可，不需要登入、不需要安裝任何東西。

## 之後的維護

- **資料自動更新**：排程會在每月 2、5、10 日台灣時間早上 9 點自動執行，資料有變動才會更新網頁，
  不需要手動操作。
- **想立刻更新一次**：到 **Actions** 分頁，手動按「Run workflow」。
- **收到「workflow 已停用」的通知信**：如果這個專案很久沒有變動，GitHub 會自動暫停排程。
  收到信時，進入 **Actions** 分頁，按「Enable workflow」重新啟用即可。
- **如果排程執行失敗**：進入 **Actions** 分頁點進失敗的那次執行，看紅字的錯誤訊息。常見原因與對策
  請參考 `計畫書.md` 第 9 節「已知風險」。失敗時不會覆蓋舊資料，網頁仍可正常使用舊的一份。

## 本機測試（不想直接上線、想先看看網頁長什麼樣）

在 `線上版/` 資料夾裡執行：

```bash
python3 -m http.server 8000
```

然後用瀏覽器開啟 `http://localhost:8000/`。

## 手動重新整理資料（不透過 GitHub Actions）

```bash
python3 scripts/build_data.py
```

執行後若資料有變動，`data/nhi.json` 會被更新；沒有變動則不會改動檔案。

## 驗證三同分組規則是否正確

```bash
python3 tests/verify_groups.py
```

這會重新用獨立邏輯計算分組結果，比對計畫書第 7 節的驗收數字（Crestor、Plavix、Depakine Chrono 等案例）。

## 重要提醒

- 這個資料夾裡**不含任何進價、進貨、廠商資料**，請勿把業主自己電腦上的本機版（含進貨資料）檔案放進來，
  也不要把本機版的程式碼複製貼上到這裡。
- 修改三同判斷規則（計畫書第 2、5 節）前，請先確認過再動手，並同步更新驗收數字。
