# 企业数字资产 AI 管理平台演示资料

这组虚构资料围绕“星河内容工作室”的城市漫游栏目，把选题文档、封面规范、设计提案和拍摄培训串成一个可问答的内容生产流程。资料中的公司、人员与业务安排仅用于演示。

生成器只使用本地字体、Pillow、PyMuPDF 和 FFmpeg，不调用在线模型或下载资源。它输出四份可入库资料：

| 文件 | 内容 |
| --- | --- |
| `01_九月城市漫游选题方案.txt` | 负责人、发布平台、排期、审核流程和归档规则 |
| `02_城市漫游封面规范.pdf` | 带中文文字层的单页规范，包含配色、尺寸和审核要求 |
| `03_城市漫游封面提案.png` | “周末去散步”城市公园插画封面 |
| `04_拍摄流程培训.mp4` | 12 秒培训视频：前 6 秒检查收音与电量，后 6 秒拍摄开场口播 |

在仓库根目录运行，以下 macOS 字体路径可替换为本机的中文字体。生成的二进制文件放在被 Git 忽略的 `runtime/content-demo` 中。

```bash
mkdir -p runtime/content-demo
docker run --rm --network none \
  --entrypoint python \
  -v "$PWD/demo:/demo:ro" \
  -v "$PWD/runtime/content-demo:/fixtures" \
  -v "/System/Library/Fonts/STHeiti Medium.ttc:/fonts/chinese.ttc:ro" \
  "$(docker compose images -q backend)" \
  /demo/create_content_demo.py --output /fixtures --font /fonts/chinese.ttc
```

也可以在已安装依赖的 Python 环境中运行：

```bash
python demo/create_content_demo.py \
  --output runtime/content-demo \
  --font /path/to/chinese-font.ttf \
  --company 星河内容工作室
```

可用 `--narration /path/to/local-audio.wav` 加入本地生成的中文旁白，建议将第一步安排在前 6 秒、第二步安排在后 6 秒。音轨会补齐或截断到 12 秒。未提供旁白时输出无声字幕视频，不自动访问语音服务。

`manifest.json` 包含文件清单、预期事实、视频时间点和示例问题；`.build/` 保存视频画面与 PDF 预览，供视觉检查。只把四份资料上传到资产库，清单和预览无需入库。重复运行会重建同名文件；请勿将真实资料保存到生成目录。

生成后导入正在运行的本地系统：

```bash
python3 demo/load_demo.py --directory runtime/content-demo
```

导入脚本等待四份资料完成索引；同名但内容不同的已存资料不会被覆盖。使用非默认账号时设置 `DEMO_USERNAME` 和 `DEMO_PASSWORD` 环境变量。导入后可运行 `python3 demo/verify_demo.py`，自动验证四类业务问题并保存演示会话。

2026-09-17 已在本地 Docker 中验证四份资料入库和四条真实业务问答，包含中文视频语音。问答可返回负责人、排期、封面色值与尺寸、封面内容和拍摄步骤，并保存来源引用。

可以试问：

- 城市漫游由谁负责，每周什么时候发布？
- 城市漫游封面的主色和尺寸是什么？
- 周末去散步封面上画了什么？
- 拍摄培训视频里，检查收音和电量之后要做什么？
