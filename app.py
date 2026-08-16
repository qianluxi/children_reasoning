"""Web 启动入口。

用法：
    python app.py            # 默认 http://127.0.0.1:5000
    python app.py --port 8080
"""
from __future__ import annotations

import argparse

from web.app import create_app


def main():
    parser = argparse.ArgumentParser(description="儿童逻辑推理训练软件 Web 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    print(f"🧩 小小推理家已启动：http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
