"""The episode-slice test over the forms a 感想 post writes its own number in.

`Recap._slice_and_why` decides whether a fetched page is about the episode he
watched, and it was the binding constraint on how complete an account of an
episode could get: it looked for `第7話` and nothing else, so a post titled
`#07`, `７話`, `07話`, `Episode 7` or by the episode's own subtitle was dropped,
and on three readings of one episode it dropped two thirds of what the search
found. It is also the test that refuses a shop's listing page for the same
episode, whose heading names it perfectly and whose body is prices -- so
loosening it needs both halves proved, which is what this does.

No network, no model, no save: fixtures in this file and the parser.

    python tools/episode_slice_test.py

spec: docs/recap.md section 3d
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config          # noqa: E402
from sim.recap import Recap        # noqa: E402

# a paragraph of scene content, reused so every fixture differs only in how it
# says which episode it is
BODY = ("　海雄とひおたんが出勤してくると、すでに先生が出勤していた。ジャージが数日変わっていない"
        "ことに海雄が気づき、家に帰っていないのではないかと指摘する。先生は新人賞に投稿する"
        "マンガの原稿を描いており、締め切りが近く通勤の時間がもったいないので店舗に泊まり込んで"
        "いた。布団部屋で完全装備のまま原稿に取り組んでいるが、進み方は悪く締め切りまでカツカツ"
        "である。カントクとつもりんも手伝うことになり、店の裏で徹夜が始まった。"
        "先生はカップ焼きそばを順番を間違えて作り、湯を切らずにソースを入れてしまう。"
        "それでもあるものだけで味付けをして食べ、うまいと言い張る。"
        "原稿にインクをこぼし、ウェットティッシュと流し台で拭こうとして余計に広げてしまう。"
        "ひおたんは呆れ、カントクは写真を撮ろうとして怒られる。"
        "夜が明けるころ、先生は泣きながら原稿を封筒に入れ、みんなで郵便局まで送り出した。"
        "帰り道でひおたんが女子力の話を持ち出し、先生の女子力はマイナスだと結論が出る。"
        "最後に店に戻ってシャッターを開け、いつもの一日が始まった。"
        "Bパートは店の裏の休憩室から始まる。フーちゃんが差し入れの菓子を配り、"
        "海雄は棚の並べ替えを任される。カントクは新刊の見本誌を抱えて戻ってきて、"
        "つもりんに写真を撮らせようとして断られる。"
        "夕方には客足が落ち、先生とひおたんが女子力の話をもう一度持ち出す。"
        "先生が眼鏡を外すと誰だか分からなくなり、それが一番の落ちになった。おわり。")

# the same page, headed nine ways
HEADS = (("第7話 in full", "エグザンプル 第7話「いざ銭湯へ……／胸がいっぱい」 感想", "第7話"),
         ("第７話 in full-width digits", "エグザンプル 第７話 感想まとめ", "第7話"),
         ("７話 with no 第", "エグザンプル ７話 「いざ銭湯へ……」 感想まとめ", "7話"),
         ("07話", "エグザンプル 07話 感想", "7話"),
         ("#07", "エグザンプル #07「いざ銭湯へ……／胸がいっぱい」", "#7"),
         ("＃０７ in full-width", "エグザンプル ＃０７ 感想", "#7"),
         ("EP7", "Example Show EP7 impressions", "EP7"),
         ("Episode 7", "Example Show Episode 7 review", "EP7"),
         ("7話目", "エグザンプル 7話目の感想", "7話"),
         ("その7", "エグザンプル その7 感想", "その7"))

# a subtitle and no number anywhere: the case nothing could catch
SUBTITLE_HEAD = "エグザンプル「宿はなし／Secret Paradise」 感想【画像あり】"

# what must still be refused: a shop's page for the right episode, whose
# heading is perfect and whose body is a price and a button
# `第9話` on the heading and volume 9 of the MANGA in the body is the fault
# this half of the test was written for: a bookstore's page for a volume was
# once stored as the episode's synopsis. LONG on purpose, so it is refused for
# having no sentences rather than for being short.
LISTING_HEAD = "エグザンプル 第7話 関連書籍・グッズ通販 | オンライン書店"
LISTING_BODY = ("エグザンプル（全12話）関連商品。 在庫あり 送料無料 ポイント3倍 "
                + " ".join(f"エグザンプル 第{n}巻 コミック 704円（税込） "
                           f"ポイント7pt 在庫あり 発売日 2014/1{n % 10} "
                           f"出版社 メディアファクトリー 著者 水あさと "
                           f"カートに入れる ほしい物リストに追加 試し読み レビュー0件"
                           for n in range(1, 13)))

# ...and a whole-series post with a section per episode, headed by the number
# in a form the old test did not know: the slice has to be the right section
SERIES_PAGE = ("エグザンプル 全話感想\n"
               "#05 先生の話。ここは第5話の中身で、温泉には行かない。ひおたんが店番をする。\n"
               "#06「宿はなし／Secret Paradise」 " + BODY + "\n"
               "#07 大江戸温泉物語へ行く回。番台さんの着物が可愛いと評判になる。\n")


def main():
    cfg = Config("config.json")
    r = Recap.__new__(Recap)
    r.config = cfg
    fails = []

    def check(label, ok, note=""):
        print(("  ok   " if ok else "  FAIL ") + label + (f"  --  {note}" if note else ""))
        if not ok:
            fails.append(label)

    print("[slice] the number in the page's own heading, and the body silent about it")
    for name, head, want in HEADS:
        seg, why = r._slice_and_why(BODY, 7, {}, head)
        form = r._names_episode(head, 7)
        check(f"a post headed {name} is about ep7",
              bool(seg) and form == want, why or f"form {form!r}, {len(seg)} chars")

    print("[slice] the same heading, asked about the wrong episode")
    for name, head, _want in HEADS:
        seg, why = r._slice_and_why(BODY, 9, {}, head)
        check(f"a post headed {name} is NOT about ep9", not seg, why[:70])

    print("[slice] the episode's own subtitle, with no number anywhere")
    titles = {6: ["宿はなし", "Secret Paradise"], 7: ["いざ銭湯へ……", "胸がいっぱい"]}
    seg, why = r._slice_and_why(BODY, 6, titles, SUBTITLE_HEAD)
    check("a post headed by ep6's part titles alone is about ep6", bool(seg), why)
    seg, why = r._slice_and_why(BODY, 7, titles, SUBTITLE_HEAD)
    check("the same post is NOT about ep7", not seg, why[:70])
    seg, why = r._slice_and_why("「宿はなし」の回。" + BODY, 6, titles, "感想")
    check("a subtitle in the BODY and nothing in the heading is about ep6", bool(seg), why)

    print("[slice] the content test still refuses a listing")
    seg, why = r._slice_and_why(LISTING_BODY, 7, {}, LISTING_HEAD)
    check("a shop's listing headed 第7話 is refused", not seg, why[:90])
    check("...and the refusal names the form it was taken on",
          "第7話" in why and "listing" in why, why[:90])

    print("[slice] a whole-series post, one section per episode, headed #0n")
    seg, why = r._slice_and_why(SERIES_PAGE, 6, titles, "エグザンプル 全話感想")
    check("the ep6 section is the one cut", bool(seg) and "焼きそば" in seg, why or seg[:60])
    check("...and it stops before the ep7 section",
          "大江戸温泉" not in seg, (seg or "")[-60:])
    seg7, why7 = r._slice_and_why(SERIES_PAGE, 7, titles, "エグザンプル 全話感想")
    check("the ep7 section is the ep7 one",
          bool(seg7) and "大江戸温泉" in seg7 and "焼きそば" not in seg7, why7 or seg7[:60])

    print("[slice] what has always been true stays true")
    seg, why = r._slice_and_why("第7話 " + BODY, 7, {}, "")
    check("a body carrying 第7話 needs no heading at all", bool(seg), why)
    seg, why = r._slice_and_why(BODY, 7, {}, "エグザンプル 第12話 感想")
    check("a post headed with another episode is refused", not seg, why[:70])
    seg, why = r._slice_and_why("", 7, {}, "第7話")
    check("an empty page is refused", not seg, why)

    print(("[slice] OK" if not fails else f"[slice] {len(fails)} FAILURE(S)"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
