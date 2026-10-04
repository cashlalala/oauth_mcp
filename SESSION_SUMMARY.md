# 工作階段摘要

日期：2026-10-05

## 目標

依照 `Spec.md` 實作一個以 OAuth 2.0 保護的遠端 MCP 伺服器：使用 Python FastMCP，
以 GitHub 作為授權伺服器，工具本身只是測試用的假功能，重點放在授權流程。

## 目前狀態

| 項目 | 狀態 |
| --- | --- |
| 伺服器實作 | 完成 |
| 單元測試 | 8 個全部通過 |
| 真實 GitHub 登入（端到端） | 已驗證成功 |
| MCP Inspector CLI 測試 | 已驗證成功 |
| Docker 映像檔 | 可建置，容器實測正常 |
| Kubernetes 設定檔 | 已撰寫，尚未在叢集上套用 |
| 推送到 GitHub | 尚未完成，三個 commit 都只在本機 |

## 做了什麼

### 1. 實作伺服器

- [server.py](server.py)：以 Streamable HTTP 提供服務，有三個假工具 `echo`、`add`、`whoami`。
- 使用 FastMCP 4.0.11 內建的 `GitHubProvider`。
- GitHub 不支援動態用戶端註冊，所以伺服器居中代理：
  - 對 GitHub 而言，伺服器是 OAuth 用戶端，持有 OAuth App 的 client ID 與 secret。
  - 對 MCP 用戶端而言，伺服器是授權伺服器兼資源伺服器。
  - 用戶端拿到的是伺服器自己簽發的 JWT，GitHub 的 token 不會離開伺服器。
- 設定全部來自環境變數，範本在 [.env.example](.env.example)。

### 2. 測試

- [tests/test_auth.py](tests/test_auth.py)：涵蓋 401 挑戰、兩份 metadata 文件、用戶端註冊、
  authorize 轉址，以及無效 token 被拒絕。不需要真實的 GitHub 憑證。
- 你填好 `.env` 之後，用 FastMCP 用戶端跑完整流程：瀏覽器登入 GitHub 後，
  `whoami` 回傳了 `cashlalala` 與 `read:user` 權限。

### 3. MCP Inspector CLI 測試

- 指令與輸出記錄在 [INSPECTOR_TESTING.md](INSPECTOR_TESTING.md)。
- 未帶 token 時被拒絕（`auth_required`）；登入後 `tools/list` 與三個工具呼叫都成功。
- 過程中發現的事：
  - 要用 `@latest`。不加版本時，這台機器會解析到已棄用的 v1，其 CLI 不支援 OAuth。
  - Inspector 2.9.0 要求 Node 22.19 以上，本機是 22.16，會出現警告但可正常執行。
  - 在沒有終端機的環境要設 `MCP_AUTO_OPEN_ENABLED=true` 才會開啟瀏覽器。
  - 登入後無法用這個方式測試錯誤 token，因為 Inspector 會改用已儲存的 token。
  - `--list-stored-auth` 顯示沒有已儲存的伺服器，原因未查。

### 4. Docker 與 Kubernetes

- [Dockerfile](Dockerfile)：`python:3.14-slim`，以非 root 使用者執行，OAuth 狀態存在 `/data`。
- [k8s/deployment.yaml](k8s/deployment.yaml) 與 [k8s/service.yaml](k8s/service.yaml)：
  單一副本，映像檔名稱暫用 `oauth-mcp:dev`，憑證從名為 `oauth-mcp-github` 的 Secret 讀取。
- 把測試用套件移到 [requirements-dev.txt](requirements-dev.txt)，映像檔只安裝執行所需的套件。
- 容器實測：以唯讀根檔案系統執行，401 挑戰與用戶端註冊都正常。
- 這台機器連不到任何叢集，所以設定檔只做了 YAML 解析與欄位對應檢查。

### 5. 收尾

- 依你的要求停止了本機伺服器，8000 埠已釋放。

## Git 紀錄

| Commit | 內容 |
| --- | --- |
| `8c3bef2` | 新增以 GitHub 做 OAuth 保護的遠端 MCP 伺服器 |
| `089beee` | 記錄 MCP Inspector CLI 測試指令 |
| `8da0353` | 新增 Dockerfile 與 Kubernetes 設定檔 |

## 待辦事項

1. **推送到 GitHub。** 權限檢查擋下了我新增 remote 的動作，請自行執行：

   ```powershell
   git remote add origin https://github.com/cashlalala/oauth_mcp.git
   git push -u origin main
   ```

2. **更換 GitHub 密碼。** `Spec.md` 裡有明文密碼，而且已經出現在這次對話中。
   我已把 `Spec.md` 加入 `.gitignore`，它不在任何 commit 裡，但仍建議更換密碼並從檔案中移除。

3. **部署到 Kubernetes 之前：**
   - 把映像檔推到你的 registry，並替換 `oauth-mcp:dev`。
   - 建立 `oauth-mcp-github` Secret（指令在 [README.md](README.md)）。
   - 把 `BASE_URL` 從佔位的 `https://mcp.example.com` 改成實際網址，
     並把 GitHub OAuth App 的 callback 設為 `{BASE_URL}/auth/callback`。
   - 目前只有 `ClusterIP` Service，要對外提供服務還需要 Ingress 或 Gateway。

## 已知限制

- **只能單一副本。** OAuth 狀態存在 pod 的磁碟上，要水平擴充需要改用 Redis 之類的共用儲存。
- **pod 被替換後狀態會消失。** `/data` 用的是 `emptyDir`，用戶端需要重新登入；
  改用 PersistentVolumeClaim 可以保留。
- **我沒有替你註冊 GitHub OAuth App。** 這裡沒有瀏覽器，而且 OAuth App 只能在網頁介面建立，
  這一步是你自己完成的。
