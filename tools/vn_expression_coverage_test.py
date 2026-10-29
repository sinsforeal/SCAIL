"""Every Momoka expression index resolves to its paired portrait and sprite.

    python tools/vn_expression_coverage_test.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from channels.vn_expression import VnExpression  # noqa: E402


def main():
    with open(os.path.join(ROOT, "config_momoka.json"), encoding="utf-8") as f:
        cfg = json.load(f)["vn"]
    expr = VnExpression(cfg, root=ROOT)
    assert expr.costume_ids() == [f"CD{i:02d}" for i in range(1, 8)]
    for costume in expr.costume_ids():
        assert len(expr.variants_by_costume[costume]) == 16, costume
        for index in range(1, 17):
            face = f"{costume}A{index:03d}"
            assert all(face + suffix in expr.labels for suffix in ("", "L", "M"))
            got = expr.resolve({"face_index": index}, costume=costume)
            spec = expr.sprite_tags[face + "L"]
            assert got["costume"] == costume and got["face"] == face
            assert got["tag"] == face + "L" and got["base_tag"] == spec["base"]
            assert got["diff_tag"] == spec.get("diff")
            assert os.path.isfile(got["face_file"])
            assert os.path.isfile(got["base_file"])
            if got["diff_tag"]:
                assert os.path.isfile(got["diff_file"])
        for feeling in ("smile", "laugh", "surprise", "excited", "talk",
                        "neutral", "sad", "worried"):
            got = expr.resolve({"expression": feeling}, costume=costume)
            assert got["costume"] == costume, (costume, feeling, got["face"])
        separate = expr.resolve({"face_index": 8, "portrait_index": 16}, costume=costume)
        assert separate["tag"] == f"{costume}A008L"
        assert separate["face"] == f"{costume}A016"
    source_style = expr.resolve({"face_index": 3, "portrait_id": "CD02A002"},
                                costume="CD07")
    assert source_style["tag"] == "CD07A003L" and source_style["face"] == "CD02A002"
    print("all 336 portrait/large/medium labels, 112 outfit/index pairs, and 56 moods resolve")


if __name__ == "__main__":
    main()
