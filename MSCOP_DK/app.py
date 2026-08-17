"""小小推理家 · ModelScope 创空间 Docker 版启动入口。

与本地 Flask Web 界面完全一致（同一套 web/ 模板与 API）。
适配创空间 Docker 运行时：
    · 必须监听 0.0.0.0；
    · 端口优先读平台注入的 PORT 环境变量，缺省 7860
      （创空间约定：容器对外端口 7860，平台用 8080 反代）。
"""
from __future__ import annotations

import os
import sys

from web.app import create_app


def _port() -> int:
    """解析 PORT 环境变量；兼容 "7860" / "7860,8080" 等平台写法。"""
    raw = os.environ.get("PORT", "7860")
    first = str(raw).split(",")[0].strip()
    try:
        return int(first)
    except ValueError:
        return 7860


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    host = os.environ.get("HOST", "0.0.0.0")
    port = _port()
    app = create_app()
    print(f"🧩 小小推理家（ModelScope Docker 版）已启动：http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
