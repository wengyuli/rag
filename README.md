# 企业数字资产库 · 本地 Docker 部署

基于 rogers0602 的 [llamaindex_rag 后端](https://github.com/rogers0602/llamaindex_rag)和 [llamaindex_rag_front 前端](https://github.com/rogers0602/llamaindex_rag_front)，整理为同一个仓库，提供已在 Apple Silicon Mac 上验证的 Docker 部署配置。

以虚构自媒体公司“星河内容工作室”为演示场景，统一管理选题策划文档、封面图片、拍摄和剪辑视频，并从资料中检索回答。前端、后端、数据库和 Ollama 均在 Docker 中运行，图片理解与语音识别使用本地模型。这是多媒体 RAG 扩展，不需要训练或微调模型权重。

## 可以做什么

- **文档**：PDF、DOCX、PPTX、XLSX、CSV、TXT、Markdown 解析入库。PDF 回答保留页码，扫描页通过本地视觉模型识别。
- **图片**：JPG、JPEG、PNG、WebP 描述可见设备、部件和文字，回答可打开原图核对。
- **视频**：MP4、MOV、WebM、MKV 均匀抽帧分析，同时用本地 Whisper 转写语音。回答保留画面或语音的时间点，点击引用可定位播放。
- **资料管理**：按名称搜索、按类型筛选、上传进度、后台解析状态、失败重试、原文件预览或下载、删除资料及检索索引。
- **团队权限**：管理员管理全部资料并上传公共资料；成员读写本部门资料并读取公共资料。列表、原文件、缩略图和送入模型的检索片段都会检查权限。

上传后先显示“排队中 / 处理中”，变为“可问答”后再提问。同名文件不会自动覆盖已有资料。任务保存在数据库中；服务重启后会重新领取未完成任务并清理部分索引，已完成的画面识别结果可以复用。当前采用一个串行解析进程，适合本机试用和小团队验证。

## 自媒体工作室演示

演示资料包括“九月城市漫游选题方案”“城市漫游封面规范”“城市漫游封面提案”和“拍摄流程培训”，覆盖策划、设计、拍摄和发布审核。生成与导入方式见 [demo/README.md](demo/README.md)。样例是虚构资料，生成文件与运行数据不提交到 Git。`tests/` 下的底层回归测试会另行添加设备测试资料；体验自媒体场景时使用 `demo/` 的生成、导入与验证流程。

## 首次部署

准备 Docker 和 Docker Compose、Python 3、curl。Python 和 curl 仅用于生成配置与下载模型；应用服务都在容器中运行。
首次构建和模型下载需要联网，并需要为模型和镜像预留磁盘空间。

```sh
git clone https://github.com/wengyuli/rag.git
cd rag
./setup.sh
```

脚本会生成随机数据库密码和 JWT 密钥，保存到权限为 600 的 `.env`；已有 `.env` 不会被覆盖。
随后启动数据库和 Ollama、下载模型、构建并启动前后端。

| 入口 | 地址或凭据 |
| --- | --- |
| 网页 | http://127.0.0.1:8090 |
| API 文档 | http://127.0.0.1:8091/docs |
| 本地试用用户名 | `admin` |
| 本地试用密码 | `admin123` |

当前登录代码使用用户名 `admin`，不是上游 README 中的邮箱。使用自己的资料前请修改试用密码。
配置仅绑定本机回环地址，适合本地功能试用，未完成生产安全加固。

## 启动、停止与验证

```sh
./start.sh
./status.sh
./stop.sh

# 查看日志
docker compose logs --tail=100 backend ollama

# 服务就绪后，执行虚构测试文档的完整问答验证
python3 tests/smoke.py

# 生成虚构的设备图片、10 秒有声视频和扫描 PDF（模型服务就绪后）
docker compose run --rm --no-deps -v "$PWD/tests:/tests:ro" -v "$PWD/runtime/test-media:/fixtures" backend python /tests/create_media_fixtures.py --output /fixtures
python3 tests/multimodal_smoke.py
```

停止后会保留数据库、文档和模型。`docker compose down -v` 会删除数据库和 Ollama 模型卷，日常停止请使用 `./stop.sh`。
默认 Compose 项目名为 `rag`。若本机已有其他服务占用 8090/8091，可使用独立名称和端口：

```sh
COMPOSE_PROJECT_NAME=rag-test WEB_PORT=8092 API_PORT=8093 ./setup.sh
```

后续启停也应保留相同环境变量，或将它们写入生成的 `.env`。

## 模型与数据

| 用途 | 模型或组件 |
| --- | --- |
| 对话 | Ollama `qwen2.5:3b` |
| 向量化 | Ollama `bge-m3`，1024 维 |
| 重排序 | `BAAI/bge-reranker-base` |
| 图片 / 视频画面 | Ollama `qwen3-vl:4b-instruct` |
| 视频语音 | `Systran/faster-whisper-small`，CPU / int8 |
| 视频处理 | FFmpeg |
| 存储 | PostgreSQL 16 + pgvector |
| 网页 | Vue 3 + Nginx |
| 后端 | FastAPI + LlamaIndex + CPU PyTorch |

Mac Docker 环境中使用 CPU 推理。Ollama 云功能已关闭，应用问答连接容器内的模型服务。

- 上传文件：`runtime/files/`
- 重排序模型：`runtime/models/bge-reranker-base/`
- 语音模型：`runtime/models/faster-whisper-small/`，版本与 SHA-256 见 `whisper-manifest.json`
- 新资料原文件与解析缓存：`runtime/files/_assets/`；旧版本文件路径继续兼容
- 重排序模型固定版本与 SHA-256：`models-manifest.json`；下载脚本逐个校验文件，并将清单写入 `runtime/bge-reranker-base-manifest.json`
- 数据库卷：`rag_pg_data`
- Ollama 模型卷：`rag_ollama_data`

模型文件、`.env`、上传文件、对话数据库、日志和生成的测试报告均不提交到 Git。

## 界面语言

登录页右上方和侧边栏底部可选择 **简体中文 / English**，默认简体中文。切换后立即更新页面、按钮、提示、日期和图表标签，浏览器记住选择，刷新页面和退出登录后仍保留。

语言切换只影响界面；文件名、上传资料、用户创建的部门名称、已有问题和回答保持原文。AI 问答可直接使用中文或英文提问。

翻译集中在 `llamaindex_rag_front/src/i18n/messages/`。运行 `cd llamaindex_rag_front && npm run test:i18n` 可检查语言恢复、即时切换、插值和译文完整性。

已验证：6 项语言测试通过；浏览器实测中英文双向切换、刷新与退出后保留语言、英文重新登录、资料列表/PDF 预览/聊天引用/资源图表/管理页面，以及切换时保留未发送的问题。

## 文件列表与资源监控

资料库使用列表展示，包含媒体类型图标、文件名、大小、上传时间、所属资料库/上传者、解析状态与操作。保留名称搜索、类型筛选、预览、失败重试和删除；详细摘要与解析提示可按行展开。

管理员可在左侧“资源监控”查看真实 CPU、内存和磁盘容量，每 2 秒采样，并显示最近 2 分钟趋势。可暂停页面刷新或手动更新；服务重启后趋势重新累计，尚未采集或不可用的数据不会显示为零。

- CPU、内存来自后端可见的 Linux 运行环境。本机 OrbStack 对应 **Docker 虚拟机**，并非 Mac 整机；其他容器的负载也会计入该环境。
- 磁盘容量来自 `runtime/files` 所在文件系统，表示该存储卷的总量、已用和剩余空间，不等于上传文件的总大小。
- 后端容器内存单独标注；它只代表后端容器，可能包含文件缓存，不包含 Ollama 等其他容器的独立用量。
- 监控 API 为 `GET /api/system/metrics`，仅管理员可访问。无需挂载 Docker socket，不读取业务资料内容。

## 当前限制

- 单文件最多 **128 MB**；视频最多 **5 分钟**，最多取 **6 个画面**。视频使用原文件在浏览器播放，浏览器不支持的编码可下载查看。
- PDF 最多 200 页，其中需要视觉识别的扫描页最多 20 页；较大文件请分段上传。DOCX/PPTX 中的嵌入图片目前不单独理解。
- 视频画面是采样，不保证覆盖短暂动作；语音转写、细小文字、仪表读数和表格可能出错。引用回原始资料用于核对，不能把生成的操作步骤当作已完成的安全检查。
- 默认 Mac Docker 使用 CPU；图片、视频及扫描页首次解析可能需要数分钟。上传和问答共享本机模型资源，并发能力尚未压测。
- 资料搜索目前按文件名筛选；语义内容检索在 AI 问答中进行。暂不包括在线文件编辑、音频单独上传、全文审阅审批或视频剪辑。
- 首次模型下载需要联网；处理资料时使用容器中的本地服务，未配置外部 AI API。Whisper 部署方式参考 [faster-whisper 官方说明](https://github.com/SYSTRAN/faster-whisper)。

## 已验证范围

2026-09-16，在 24GB 内存的 Apple Silicon Mac、OrbStack Docker 环境实测：

- 登录、上传 TXT、文档列表与原文读取通过。
- 问答正确返回虚构蓝鲸项目的负责人“林晓”和交付周期“17 个工作日”，且引用正确文件。
- 会话持久化、网页历史会话、点击引用查看原文通过。
- 小文档上传约 3.1 秒，单次问答约 9.1 秒，整轮 API 验证约 12.4 秒。

以上为一次小文档测试，不代表大文档或并发性能。此处为升级前文档基线。多媒体版本验证范围见下方；复杂表格、旧版 Office、LDAP 和多人并发尚未验证。
测试脚本会保存本机结果到 `tests/latest-smoke.json`。当时的依赖版本留存在 [docs/python-dependencies-tested.txt](docs/python-dependencies-tested.txt)，这是实测快照，当前 Dockerfile 安装时仍由依赖解析器选择版本。

### 2026-09-17 多媒体版本实测

- 图片、10 秒有声视频、2 页无文字层扫描 PDF：真实本地模型解析、向量索引、原文件下载与缩略图通过。
- 图片和扫描 PDF 问答正确返回 `WIDGET ZX-17` 与 `0.6 MPa`；视频问答正确返回“关闭蓝色阀门，再按绿色按钮”。实时来源与历史保存一致，并保留视频时间点及 PDF 页码。
- 本机首次处理这三份虚构资料并完成三次问答共约 **298 秒**；该视频采样了 2 帧。测试素材的画面文字和合成语音为英语，提问和回答为中文。这不是长视频或多人并发性能承诺。
- 新版停顿分段在禁网 CPU 容器中实测，将两步语音分别定位为 `0.00–2.12` 秒和 `4.91–6.95` 秒。
- 33 项隔离测试通过，覆盖解析、失败降级、上传大小及格式、重复上传、权限、重试、恢复、视频 Range 206/416 和引用去重。测试使用临时 SQLite 与线程锁模拟事务锁，未覆盖 PostgreSQL 多实例断线故障切换。
- 浏览器实测：图片/视频预览、自动进度、类型筛选、名称搜索、旧资料与旧聊天引用兼容通过。

可在后端镜像中运行隔离测试（不会访问业务数据库或模型服务）：

```sh
docker run --rm --network none -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -v "$PWD:/repo:ro" -w /repo "$(docker compose images -q backend)" python -m unittest discover -s tests -p 'test_*.py' -v
```

### 2026-09-17 文件列表与资源监控实测

- 完整 45 项隔离测试通过，包含新增的 12 项 CPU 计数、内存口径、磁盘、历史采样、生命周期与管理员权限测试。
- 本地 Docker 实测：未登录访问监控接口返回 401；管理员能读取真实指标，采样时间每 2 秒递增，保留最多 60 个点。
- 浏览器验证：新系统名称、文件列表、文件名搜索、展开详情与图片预览通过；资源卡片、趋势图、暂停/手动/恢复刷新、切换页面后的暂停状态保持通过。
- 原有 4 份自媒体演示资料保留；上传时间以浏览器本地时区显示。

## 升级现有安装

升级前备份 PostgreSQL 数据库与 `runtime/files/`。启动时自动添加媒体字段，保留旧文档和聊天记录，不清空数据。然后执行 `./setup.sh` 下载新增视觉与语音模型并构建镜像。

不要改变已有数据库的 `DB_PASSWORD`，也不要为了升级删除数据卷。若需要回退应用代码，先停服务再切换到升级前提交；新增数据库列可以保留。

## 本仓库调整

- 将前后端源码放在同一个仓库，并使用根目录 `compose.yaml` 部署。
- 修正构建路径，提供独立端口，省略上游的演示 LDAP 服务。
- 选择 CPU 版 PyTorch，补充 python-pptx、sentencepiece 和 libmagic。
- 补齐固定版本与 SHA-256 校验的模型下载、配置初始化和启停脚本。
- 修正管理员种子数据插入后的用户 ID 序列。
- 上传接口限制 128 MB，Nginx 为 multipart 请求保留少量额外空间；问答代理超时为 600 秒。

前后端目录中的原始 Docker/Compose 文件保留作上游参考；部署请使用根目录配置。

## 来源与许可说明

源仓库、固定提交与授权声明见 [THIRD_PARTY.md](THIRD_PARTY.md) 和 [UPSTREAM.txt](UPSTREAM.txt)。本仓库保留上游代码中的作者信息与原始 README；不将上游代码声明为自行原创。
