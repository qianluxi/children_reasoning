# 小小推理家 · Docker 部署（与本地完全一致的 Flask Web 界面）
# 运行时只装 Flask Web + 图形渲染依赖（题库已打包，无需 reasoning-gym）
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --timeout 120 --retries 5 \
    "flask>=3.0" "pillow>=10.0" "PyYAML>=6.0"

# 应用代码
COPY app.py cli.py ./
COPY logic_kids ./logic_kids
COPY web ./web
COPY config ./config

# 外部题库（BIG-bench / LogiQA / Reasoning Gym，审核通过，含中文儿童版）
COPY data/external ./data/external

EXPOSE 5000
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]
