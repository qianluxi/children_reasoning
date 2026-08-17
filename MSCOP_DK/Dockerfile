# 小小推理家 · ModelScope 创空间 Docker 版
# 运行时只装 Flask Web + 图形渲染依赖（题库已打包，无需 reasoning-gym；
# 内置题库启动时自动生成，外部题库直接读 data/external）。
FROM python:3.11-slim

WORKDIR /app

# 容器内 pip 到 PyPI 容易超时：加长超时并重试
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
    "flask>=3.0" "pillow>=10.0" "PyYAML>=6.0"

# 应用代码（与仓库根目录同源，保证本地/创空间页面一致）
COPY app.py ./
COPY logic_kids ./logic_kids
COPY web ./web
COPY config ./config

# 外部题库（BIG-bench / LogiQA / Reasoning Gym，含中文与儿童化改写）
COPY data/external ./data/external

# 创空间约定：容器必须监听 0.0.0.0:7860
EXPOSE 7860
CMD ["python", "app.py"]
