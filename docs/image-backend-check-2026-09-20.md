# agy 產圖測試：2026-09-20

在本次 macOS 環境中，透過外部 `genimage-nb` skill 的 `gen-image.sh` 呼叫已登入的 agy，使用相同提示詞連續產圖三次。三次均未重試，皆成功交付 PNG；這是單機、單次工作階段的初步驗證，尚未涵蓋跨日、並行、登入失效或服務限流。

| 次數 | 耗時（秒） | 結束碼 | 檔案格式與尺寸 | 指定兩行文字 | 禁止額外文字 |
| :--- | ---: | ---: | :--- | :--- | :--- |
| 1 | 23.51 | 0 | PNG，1376×768 | 正確 | 未通過：書封與筆記增加文字 |
| 2 | 26.89 | 0 | PNG，1376×768 | 正確 | 未通過：書封與筆記增加文字 |
| 3 | 40.50 | 0 | PNG，1376×768 | 正確 | 未通過：書封增加文字 |

三張圖都檢查過 PNG 檔頭、尺寸與畫面，雜湊互不相同。平均耗時 30.30 秒。包裝程式會在需要時將原始產物轉成 PNG，因此此處驗證的是最終交付格式，不代表 agy 原生輸出就是 PNG。

提示詞如下；另附尺寸提示 `landscape 16:9 aspect ratio, high detail`。每次呼叫的 `IMGNB_TIMEOUT` 設為 180 秒，使用不同輸出檔名並依序執行，避免包裝程式的備援檔案搜尋交叉取到其他呼叫的產物。

```text
Create an academic presentation cover illustration: a notebook, a magnifying glass, and neatly arranged reference books on a desk, cream background with dark teal accents. Include exactly these two lines of Traditional Chinese text: title 「研究方法」 and subtitle 「來源查核與論證」. No other text, no logos, no watermark. Use generous margins and clearly readable typography.
```

重現方式：從目前 agent 的 skill 清單取得 `genimage-nb` 的實際路徑，依其登入與呼叫說明，以相同提示詞、不同檔名執行三次。測試圖與原始 JSON 紀錄留在執行機的暫存目錄，不放入框架的共用素材。

本輪證據顯示 agy 能連續成功產圖，尚不足以推論長期穩定性；完整文字限制三次都未通過。依維護者本次指示，框架仍保留 Codex 作為產圖後端的例外規則。若日後採用 agy，須保留逐張校對，並另外驗證實際工作所需的負載與失敗情境。
