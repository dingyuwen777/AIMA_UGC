"""从根 uv 环境或安装包运行 WisersOne 人工下载。"""

import argparse
from pathlib import Path

from aima_ugc.adapters.providers.wisersone.auth import default_host_root
from aima_ugc.adapters.providers.wisersone.export import download_wisersone_xlsx


def main() -> None:
    parser = argparse.ArgumentParser(description="WisersOne 过去24小时 Excel 下载")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--auth-dir", type=Path)
    parser.add_argument("--headed", action="store_true", help="首次登录或会话失效时打开可见浏览器")
    args = parser.parse_args()
    output = args.output_dir or default_host_root() / "aima-historical-input" / "wisersone-manual"
    result = download_wisersone_xlsx(output, auth_dir=args.auth_dir, headless=not args.headed)
    print(f"Excel 已保存：{result}")


if __name__ == "__main__":
    main()
