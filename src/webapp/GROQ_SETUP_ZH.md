# Groq 本地配置与测试

网页目前仍是 UI 演示。保存 key 不会自动启用网页 AI；原来的 OpenAI 后端草稿也没有改成 Groq。

## 先替换公开过的 key

到 https://console.groq.com/keys 撤销在聊天里公开过的 key，建立新 key。在项目根目录 `.env` 内替换 `GROQ_API_KEY` 的值。不要发到聊天或贴进浏览器代码。文件已被 Git 忽略；环境变量存在时优先使用环境变量。

## 选择模型

本次配置默认 `GROQ_VISION_MODEL=qwen/qwen3.8-27b`。根据 2026-11-08 查询的 Groq 视觉文档，这个模型支持图片输入，每次最多 3 张；账号实际可用性需要用模型列表和一次视觉请求验证。不要因为文字模型能聊天，就认为它能看照片。

官方资料：
- https://console.groq.com/docs/vision
- https://console.groq.com/docs/models

## 命令行使用

在项目根目录打开终端，运行下面命令列出 API 返回的模型；不会上传照片：

```powershell
python -m src.webapp.groq_tools models
```

上传一张你明确选择的本地照片做观察测试（会上传至 Groq，可能消耗额度／产生费用）：

```powershell
python -m src.webapp.groq_tools image "src/webapp/static/assets/mochi.jpg"
```

临时指定其他支持视觉且账号允许的模型：

```powershell
python -m src.webapp.groq_tools image "你的照片.jpg" --model "模型的完整ID"
```

长期切换模型：修改 `.env` 的 `GROQ_VISION_MODEL`。无需把 key 写进命令或安装 Groq SDK；该工具使用 Python 标准库。

401 表示 key 无效或已撤销；403 要区分 Cloudflare 1010（客户端请求被拦截）与 Groq 权限错误；404 检查模型 ID；429 检查额度或请求频率。工具使用明确的 PawLog User-Agent，并对错误内容中的 key 脱敏。不要把错误截图中的凭据发到聊天。

2026-11-08 修复默认 Python User-Agent 引起的 Cloudflare 1010 后，已成功请求真实 `/models`，返回列表包含 `qwen/qwen3.8-27b`。尚未上传图片或验证实际视觉输出。将来“全部照片选最佳图”需要遵守单次图片数量限制，分批比较，再由主人确认猫咪身份。
