"""Экспорт графа в Mermaid для документации."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph import build_pipeline


def main() -> None:
    graph = build_pipeline()
    mermaid = graph.get_graph().draw_mermaid()
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    output = docs_dir / "graph.mmd"
    output.write_text(mermaid, encoding="utf-8")
    print(f"Graph exported to {output}")


if __name__ == "__main__":
    main()
