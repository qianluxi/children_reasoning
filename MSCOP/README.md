# 小小推理家 · ModelScope 创空间版

儿童逻辑思维训练平台的 **ModelScope 创空间（Gradio）部署版**。

## 功能

- 🧠 综合挑战 / 🧩 逻辑推理 / 🔍 找规律 / 🔢 数学思维 / 🧭 空间迷宫 / 🪢 关系推理 / 📏 排序挑战
- 4 级难度（简单 / 普通 / 困难 / 挑战）
- 图形题（迷宫 / ARC 格子 / 长方形计数）自动渲染成图片
- 外部题库已打包（BIG-bench 125 + LogiQA2.0 20 + Reasoning Gym 165，含中文儿童版）
- 内置题库启动时自动生成

## 部署到创空间

1. 在 [ModelScope 创空间](https://modelscope.cn/studios) 新建空间（SDK 选 Gradio）；
2. 把本目录（`MSCOP/` 下的内容）推送到空间仓库；
3. 空间会自动安装 `requirements.txt` 并运行 `app.py`。

## 本地运行

```bash
pip install -r requirements.txt
python app.py
```

## 目录

```text
app.py                Gradio 入口
logic_kids/           核心引擎（生成/验证/难度/选题/图形渲染）
data/external/        外部题库（按来源分目录，含许可证与溯源）
config/               许可证策略与题库配额
```

> 说明：Reasoning Gym / LogiQA 数据仅用于研究与非商业用途请遵守各自许可证
> （Apache-2.0 / CC BY-NC-SA 4.0）；LogiQA 为非商业许可。
