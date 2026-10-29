# B5: bring bible_readable.md in line with the rewritten bible.json (speech guide table, mechanism table and bullets).
# render_doc needs the full build result, so the sections are re-rendered here with the tool's own row formats.
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
b = json.load(open(os.path.join(HERE, "bible.json"), encoding="utf-8"))
path = os.path.join(HERE, "bible_readable.md")
L = open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n").split("\n")


def compact(obj, maxlen=200):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if len(s) > maxlen:
        s = s[: maxlen - 1] + "…"
    return s.replace("|", "/")


def row(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


def replace_table(L, header_start, new_rows):
    i = next(k for k, x in enumerate(L) if x.startswith(header_start))
    j = i + 2
    while j < len(L) and L[j].startswith("|"):
        j += 1
    return L[: i + 2] + new_rows + L[j:]


sg = b["speech_guide"]
rows = []
for r in sg["rules"]:
    rc = dict(r["receipt"])
    rc.pop("examples", None)
    rows.append(row([r["rule"], r["class"], r["tier"], r["register"], r["evidence"], compact(rc, 130)]))
L = replace_table(L, "| rule | class | tier |", rows)
i = next(k for k, x in enumerate(L) if x.startswith("Rule split:"))
L[i] = ("Rule split: class %s; tier %s; register %s; evidence %s. Unreceipted rules: %s."
        % (sg["class_split"], sg["tier_split"], sg["register_split"], sg["evidence_split"], sg["unreceipted"] or "none"))

M = b["mechanisms"]
rows = []
for m in M["mechanisms"]:
    rset = ", ".join(x["record_id"] for x in m["receipts"][:2]) or "-"
    rows.append(row([m["name"], m["class"], m["tier"], m["confidence"], str(m["lines"]), "%s / %s" % (m["lines_non_H"], m["lines_H"]),
                     m["control_rate"], str(m["distinctive"]), rset]))
L = replace_table(L, "| mechanism | class |", rows)
i = next(k for k, x in enumerate(L) if x.startswith("Mechanism split:"))
L[i] = ("Mechanism split: class %s; tier %s (%d firm, %d thin, %d weak) over %d spoken lines."
        % (M["class_split"], M["tier_split"], M["firm_count"], M["thin_count"], M["weak_count"], M["spoken_lines"]))
i = next(k for k, x in enumerate(L) if x.startswith("Non-distinctive from the control"))
L[i] = "Non-distinctive from the control heroines: %s." % (", ".join(M["distinctive_false"]) or "none")
i = next(k for k, x in enumerate(L) if x.startswith("Every mechanism is classed") or x.startswith("The matchers and their definitions"))
L[i] = M["class_note"]
i = next(k for k, x in enumerate(L) if x.startswith("How each was counted"))
j = i + 2
k = j
while k < len(L) and L[k].startswith("- **"):
    k += 1
bul = []
for m in M["mechanisms"]:
    extra = (" " + m["note"]) if m.get("note") else ""
    bul.append("- **%s** (%s, %s, %s, %d line(s), share %s; non-H %d / H %d; control %s, distinctive %s): %s%s"
               % (m["name"], m["class"], m["tier"], m["confidence"], m["lines"], m["share_of_spoken"], m["lines_non_H"], m["lines_H"],
                  m["control_rate"], m["distinctive"], m["method"], extra))
L = L[:j] + bul + L[k:]
open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("patched", path, len(L), "lines")
