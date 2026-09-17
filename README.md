# 本地 RAG 知识库 · Docker 部署

基于 rogers0602 的 [llamaindex_rag 后端](https://github.com/rogers0602/llamaindex_rag)和 [llamaindex_rag_front 前端](https://github.com/rogers0602/llamaindex_rag_front)，整理为同一个仓库，提供已在 Apple Silicon Mac 上验证的 Docker 部署配置。

支持上传文档、知识库问答、来源引用、原文预览和历史会话。前端、后端、数据库和 Ollama 均在 Docker 中运行，使用本地模型。

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
| 存储 | PostgreSQL 16 + pgvector |
| 网页 | Vue 3 + Nginx |
| 后端 | FastAPI + LlamaIndex + CPU PyTorch |

Mac Docker 环境中使用 CPU 推理。Ollama 云功能已关闭，应用问答连接容器内的模型服务。

- 上传文件：`runtime/files/`
- 重排序模型：`runtime/models/bge-reranker-base/`
- 重排序模型固定版本与 SHA-256：`models-manifest.json`；下载脚本逐个校验文件，并将清单写入 `runtime/reranker-manifest.json`
- 数据库卷：`rag_pg_data`
- Ollama 模型卷：`rag_ollama_data`

模型文件、`.env`、上传文件、对话数据库、日志和生成的测试报告均不提交到 Git。

## 已验证范围

2026-09-16，在 24GB 内存的 Apple Silicon Mac、OrbStack Docker 环境实测：

- 登录、上传 TXT、文档列表与原文读取通过。
- 问答正确返回虚构蓝鲸项目的负责人“林晓”和交付周期“17 个工作日”，且引用正确文件。
- 会话持久化、网页历史会话、点击引用查看原文通过。
- 小文档上传约 3.1 秒，单次问答约 9.1 秒，整轮 API 验证约 12.4 秒。

以上为一次小文档测试，不代表大文档或并发性能。扫描 PDF 的 OCR、复杂表格、旧版 Office、LDAP、权限隔离和多人并发不在此次验证范围内。
测试脚本会保存本机结果到 `tests/latest-smoke.json`。当时的依赖版本留存在 [docs/python-dependencies-tested.txt](docs/python-dependencies-tested.txt)，这是实测快照，当前 Dockerfile 安装时仍由依赖解析器选择版本。

## 本仓库调整

- 将前后端源码放在同一个仓库，并使用根目录 `compose.yaml` 部署。
- 修正构建路径，提供独立端口，省略上游的演示 LDAP 服务。
- 选择 CPU 版 PyTorch，补充 python-pptx、sentencepiece 和 libmagic。
- 补齐固定版本与 SHA-256 校验的模型下载、配置初始化和启停脚本。
- 修正管理员种子数据插入后的用户 ID 序列。
- Nginx 上传上限为 50MB，问答代理超时为 600 秒。

前后端目录中的原始 Docker/Compose 文件保留作上游参考；部署请使用根目录配置。

## 来源与许可说明

源仓库、固定提交与授权声明见 [THIRD_PARTY.md](THIRD_PARTY.md) 和 [UPSTREAM.txt](UPSTREAM.txt)。本仓库保留上游代码中的作者信息与原始 README；不将上游代码声明为自行原创。
