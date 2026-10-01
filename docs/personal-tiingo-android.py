#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android/Pydroid one-tap Tiingo downloader for Market Research Terminal.

使用方法：
1. 用 Pydroid 3 打开本文件。
2. 点运行。
3. 粘贴 Tiingo API Token。
4. 程序自动下载 14 个 ETF 的 2019-01-01 至今天日线。
5. 自动生成 tiingo_personal_bundle.json，优先保存到手机 Download/下载 文件夹。

Token 只在当前程序内存中使用，不会写入输出 JSON。
仅使用 Python 标准库，无需 pip 安装任何依赖。
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

START_DATE = "2019-01-01"
END_DATE = date.today().isoformat()
TICKERS = [
    "SPY", "QQQ", "DIA",
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
    "XLP", "XLRE", "XLU", "XLV", "XLY",
]
SCHEMA = "MRT-TIINGO-PERSONAL-BUNDLE-V1"
OUTPUT_NAME = "tiingo_personal_bundle.json"


def choose_output_path() -> Path:
    """Prefer Android public Download folder; fall back to script/current folder."""
    candidates = [
        Path("/storage/emulated/0/Download"),
        Path("/sdcard/Download"),
    ]
    for folder in candidates:
        try:
            if folder.is_dir() and os.access(folder, os.W_OK):
                return folder / OUTPUT_NAME
        except OSError:
            pass

    try:
        return Path(__file__).resolve().parent / OUTPUT_NAME
    except Exception:
        return Path.cwd() / OUTPUT_NAME


def read_token() -> str:
    print("\n请粘贴你的 Tiingo API Token。")
    print("Token 只在本次运行内存中使用，不会写入 JSON。")
    try:
        token = getpass.getpass("Tiingo API Token（输入可能不显示）: ").strip()
    except Exception:
        token = input("Tiingo API Token: ").strip()
    return token


def request_symbol(symbol: str, token: str):
    query = urllib.parse.urlencode({
        "startDate": START_DATE,
        "endDate": END_DATE,
        "format": "json",
    })
    url = (
        "https://api.tiingo.com/tiingo/daily/"
        + urllib.parse.quote(symbol)
        + "/prices?"
        + query
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Token {token}",
            "Accept": "application/json",
            "User-Agent": "MarketResearchTerminal-Android/1.0",
        },
    )

    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, list) or not payload:
                raise RuntimeError(f"{symbol}: Tiingo 没有返回日K数据")
            return payload
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:240]
            if exc.code in (401, 403):
                raise RuntimeError(
                    f"{symbol}: HTTP {exc.code}。请检查 Token 是否正确/账户是否已验证。"
                ) from exc
            if exc.code == 429 and attempt < 3:
                wait_s = 10 * attempt
                print(f"  Tiingo 限速，{wait_s} 秒后自动重试…")
                time.sleep(wait_s)
                last_error = exc
                continue
            raise RuntimeError(f"{symbol}: HTTP {exc.code} {body}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < 3:
                wait_s = 5 * attempt
                print(f"  网络暂时失败，{wait_s} 秒后自动重试…")
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"{symbol}: 网络错误：{exc.reason}") from exc

    raise RuntimeError(f"{symbol}: 下载失败：{last_error}")


def pause_and_exit(code: int) -> int:
    try:
        input("\n按回车退出…")
    except Exception:
        pass
    return code


def main() -> int:
    print("=" * 58)
    print("Market Research Terminal · Android Tiingo Downloader")
    print("=" * 58)
    print(f"日期范围：{START_DATE} → {END_DATE}")
    print(f"标的数量：{len(TICKERS)}")

    token = read_token()
    if not token:
        print("\n没有输入 Token，已停止。")
        return pause_and_exit(2)

    data = {}
    try:
        for i, symbol in enumerate(TICKERS, 1):
            print(f"\n[{i:02d}/{len(TICKERS)}] 正在下载 {symbol} …")
            rows = request_symbol(symbol, token)
            data[symbol] = rows
            print(f"  完成：{len(rows)} 条日K")
    except Exception as exc:
        print("\n❌ 下载中断：")
        print(str(exc))
        print("\n不要把 Token 发给别人。你可以把上面的报错截图发给 ChatGPT。")
        return pause_and_exit(1)
    finally:
        token = ""

    bundle = {
        "schema": SCHEMA,
        "provider": "Tiingo EOD",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start": START_DATE,
        "end": END_DATE,
        "symbols": TICKERS,
        "data": data,
    }

    out_path = choose_output_path()
    try:
        out_path.write_text(
            json.dumps(bundle, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except PermissionError:
        fallback = Path.cwd() / OUTPUT_NAME
        fallback.write_text(
            json.dumps(bundle, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        out_path = fallback

    print("\n" + "=" * 58)
    print("✅ 全部完成")
    print(f"文件：{OUTPUT_NAME}")
    print(f"保存位置：{out_path}")
    print("Token 没有写入这个 JSON。")
    print("\n下一步：回到 Personal Real Data Mode → 选择/拖入这个 JSON。")
    print("=" * 58)
    return pause_and_exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
