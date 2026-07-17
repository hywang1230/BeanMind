#!/usr/bin/env python3
"""从仓库测试账本确定性生成临时 1×/2×数据，不修改输入。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from beancount import loader
from beancount.core.data import Transaction

from benchmark_ledger_projection import make_scaled_copy


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(source: Path, output: Path, scale: int) -> dict:
    source = source.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError(f"输出目录已存在，拒绝覆盖: {output}")
    output.mkdir(parents=True)
    generated = make_scaled_copy(source, scale, output)
    entries, errors, options = loader.load_file(str(generated))
    if errors:
        shutil.rmtree(output)
        raise RuntimeError("; ".join(str(error) for error in errors[:10]))
    transactions = [entry for entry in entries if isinstance(entry, Transaction)]
    included = sorted(Path(path).resolve() for path in options.get("include", []))
    return {
        "source": str(source),
        "generated": str(generated),
        "scale": scale,
        "transactions": len(transactions),
        "postings": sum(len(entry.postings) for entry in transactions),
        "files": len(included),
        "fingerprint": {
            str(path.relative_to(generated.parent)): file_digest(path)
            for path in included
            if path.exists()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/ledger/main.beancount"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.output, args.scale), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
