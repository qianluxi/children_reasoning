# 小小推理家 · ModelScope 创空间 Docker 版

儿童逻辑思维训练平台的 **ModelScope 创空间（Docker SDK）部署版**。
页面与本地 Flask Web 版**完全一致**（不是 Gradio）：儿童挑战卡片、
4 级难度、图形题自动渲染、能力画像全都有。

## 功能

- 🧠 综合挑战 / 🧩 逻辑推理 / 🔍 找规律 / 🔢 数学思维 / 🧭 空间迷宫 /
  🪢 关系推理 / 📏 排序挑战（儿童视角，隐藏数据源名）
- 4 级难度（简单 / 普通 / 困难 / 挑战），随时切换并重抽一题
- 图形题（迷宫 / ARC 格子 / 长方形计数）由程序按需渲染成图片
- 外部题库已打包：BIG-bench 125 + LogiQA2.0 20 + Reasoning Gym 165，
  含中文版与儿童化改写
- 内置题库（110 题）启动时自动生成并验证

## 部署到创空间（关键步骤）

1. 在 [ModelScope 创空间](https://modelscope.cn/studios) 点「新建空间」；
2. **SDK 类型必须选 `docker`**（不是 Gradio / Static）；
3. 把本目录（`MSCOP_DK/` 下的全部内容）推送到空间仓库：

   ```bash
   cd MSCOP_DK
   git init
   git add .
   git commit -m "children reasoning docker space"
   git remote add origin https://modelscope.cn/studios/<你的用户名>/<空间名>.git
   git push -u origin master
   ```

4. 创空间会自动执行 `docker build`，然后按镜像启动；
5. 部署完成后打开空间页面即可使用。

> Dockerfile 已按创空间约定 `EXPOSE 7860`，入口 `app.py` 监听
> `0.0.0.0` 并读取平台注入的 `PORT` 环境变量（缺省 7860）。

## 本地验证（可选）

```bash
cd MSCOP_DK
docker build -t children_reasoning_mscop .
docker run -p 7860:7860 children_reasoning_mscop
# 打开 http://127.0.0.1:7860
```

验证要点：首页应能打开，能看到「挑战类型」卡片；迷宫 / ARC / 长方形
计数题能显示图片；答案提交与提示功能正常。

## 遇到红色"错误"框怎么办

1. 打开创空间 **运行日志**，看容器启动时的报错堆栈；
2. 最常见原因是依赖安装失败（本版只装 flask / pillow / PyYAML，
   已彻底移除 reasoning-gym，题库 JSON 直接打包，运行时不需要生成器）；
3. 若日志显示端口/反代问题，确认 Dockerfile 里 `EXPOSE 7860` 未被改动；
4. 仍报错就把日志贴回来，我可以针对性修复。

## 环境变量

| 变量 | 说明 | 缺省 |
| --- | --- | --- |
| `PORT` | 容器监听端口（平台注入） | `7860` |
| `HOST` | 监听地址 | `0.0.0.0` |
| `SECRET_KEY` | Flask session 签名密钥（公网部署建议设置） | 本地开发默认值 |

## 目录

```text
app.py                Flask 入口（0.0.0.0:7860）
Dockerfile            创空间 Docker 构建（python:3.11-slim）
logic_kids/           核心引擎（生成/验证/难度/选题/图形渲染）
web/                  Flask 页面与静态资源（与本地一致）
config/               许可证策略与题库配额
data/external/        外部题库（按来源分目录，含许可证与溯源）
```

> 数据说明：Reasoning Gym / LogiQA 数据仅用于研究与非商业用途，请遵守
> 各自许可证（Apache-2.0 / CC BY-NC-SA 4.0）。
