# 电脑本地检测

在 Windows 电脑上，先安装下方的 Python 环境，并按 [模型文件说明](../../models/README.md) 放入两个权重文件。然后双击对应入口：

- `start-camera-monitor.cmd`：输入 ESP32-CAM IP，持续监测。检测到猫到访后，等约 10 秒无猫并用新画面再次确认，再执行一次排泄物检测。事件保存在 `results/auto-*/`。
- `test-cat-photo.cmd`：猫照片检测。
- `test-cat-camera.cmd`：ESP32-CAM 猫检测，输入当前 IP。
- `test-poop-photo.cmd`：排泄物照片检测。

项目根目录的 `models/` 存模型权重，`.venv/` 存 Python 环境，`.ultralytics/` 存 YOLO 套件的本机设置。`detect_cat.py` 会导入 `detect.py`，所以两个 Python 文件都需要保留。`outputs/vision/` 和 `__pycache__` 会在运行时自动生成。

旧训练资料、数据处理/评估脚本、旧结果和旧入口已移到项目根目录 `backups/ai-cleanup-时间戳/`，需要时可以恢复。归档记录供以后重新训练和评估参考。

## 猫检测（Cat Detection）

把照片拖到 `test-cat-photo.cmd` 上；或者双击 `test-cat-camera.cmd`，输入串口 `Camera Ready!` 显示的当前 IP。

从项目根目录运行：`.\.venv\Scripts\python.exe src/vision/detect_cat.py "http://摄像头IP/capture"`

使用独立的 COCO 预训练 `models/yolo26n.pt`，演示前请把权重复制到本机。只检测 `cat` 类，不覆盖排泄物模型。保留原图比例，结果写入 `outputs/vision/cat-时间戳/` 的图片和 JSON。

`cat_detected: true` 表示看见猫；`false` 只表示没检测到，遮挡或光线差可能漏检。图片读取或推理失败写入 `status: unknown`、`cat_detected: null`，退出码 1。`cleaning_allowed` 始终为 `false`：此工具不判断安全离开、不计时、不驱动电机。实际猫砂盆准确率需用现场照片验证。

AI 在这台 Windows 电脑运行，使用 `models/weights.pt`。目前只输出检测结果，不连接电机。

## 检测照片

把照片拖到 `test-poop-photo.cmd` 上。终端会打印检测结果，结果保存在 `outputs/vision/时间戳/`：

- `detection.jpg`：带检测框的图片，使用与训练一致的 640×640 拉伸输入。
- `result.json`：标签、置信度、坐标和推理时间。

`waste_detected` 支持 `waste`、`poop`、`urine` 和 `cat urine` 标签；`poop_detected` 保留兼容旧模型。`false` 只表示没有检测到目标，不保证场景中没有排泄物。失败时退出码为 1，结果视为 unknown，不触发清理。

## ESP32-CAM 单张照片

在项目根目录打开终端，替换下面网址为当前摄像头实际 IP 的快照地址（CameraWebServer 通常是 `/capture`）：

```powershell
.\.venv\Scripts\python.exe src/vision/detect.py "http://摄像头IP/capture"
```

电脑和 ESP32-CAM 需要处于互通的局域网。不要使用摄像头控制主页代替照片地址。

默认置信度暂保留 0.32，可通过 `--conf 0.5` 调整；最终阈值需要由新模型的验证集评估确定。可使用 `--model "models/新模型.pt"` 比较新权重，无需覆盖旧模型。`model_classes` 输出实际加载的模型类别，避免误用旧权重。

## 在其他电脑安装开发环境（在项目根目录执行）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

这是开发验证工具。最终产品的自动启动、手机界面和 Arduino 安全控制仍需后续集成。
