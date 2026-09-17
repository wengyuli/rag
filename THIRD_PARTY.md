# 上游来源与声明

| 组件 | 来源 | 导入提交 |
| --- | --- | --- |
| 后端 | https://github.com/rogers0602/llamaindex_rag | `8836b2f01b1852a8ace09bc9481efbd70364c3d3` |
| 前端 | https://github.com/rogers0602/llamaindex_rag_front | `f1e816008129d0fbfe12b0596cfe4860738d0fbc` |

原作者：Guo Lijian（依据源代码与上游 README 的署名）。

导入的是源码文件，未包含上游 `.git` 目录或 `.env`。保留了原始 README、源码署名、示例和截图；本地部署适配见根目录 README。

## 授权文本现状

导入提交中未找到独立 LICENSE 文件。上游 README 的许可章节声明使用 AGPL-3.0，并另述闭源商业授权；后端 README 开头另有“仅供学习交流、严禁商业用途”的文字。此处如实保留两处原文，不自行消解冲突或授予额外权利。

使用、修改和分发上游部分时应核实并遵循原作者适用的授权条件；商业使用需向原作者明确授权范围。

- [后端原始 README](llamaindex_rag/README.MD)
- [前端原始 README](llamaindex_rag_front/README.md)

模型不包含在仓库内，下载和使用模型时适用各模型发布方的条款。

## 新增媒体组件

图片和视频画面使用 [Qwen3-VL](https://ollama.com/library/qwen3-vl)；语音使用 [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small)，推理由 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 实现。模型权重均不随源码上传。组件与模型分别遵循其原始许可；FFmpeg 来自 Debian 软件包。
