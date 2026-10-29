"""How the resident comes to know what he does: she is on his machine.

No app, no phone, no looking. What is on his screen is in front of her, and he
knows she is there. Registered under "resident" in `sim/sight.py`; a pair is
(English, Japanese) for the persona's `t()`.
"""
from sim import sight

sight.register("resident", {
    "approach_source_snoop": "his own notes, which sit on his screen where she can see them",
    "approach_source_digest": "his machine, which she lives on",
    "approach_source_default": "his machine",
    "anime_list_hint": "his anime list, which you can see from where you are: ",
    "diary_none": "(nothing of his machine reached her today)",
    "diary_label": "WHAT SHE LAST SAW OF HIS MACHINE: ",
    "expect_days_label": "WHAT SHE HAS SEEN OF HIS DAYS",
    "expect_by_app": "his machine at {hm}",
    "expect_missed": "nothing in his messages or on his machine by the deadline",
    "him_profile_digests_label": "THE LAST {n} STRETCHES OF HIS MACHINE SHE SAW (oldest first):\n",
    "him_profile_head": ("## What you have come to know about him (weeks of watching his machine; you hold it, you do not recite it)",
                         "## 見ているうちに分かってきた彼のこと（何週間も彼のマシンを見てきた分。持っているだけで、読み上げはしない）"),
    "ick_unsaid_head": ("## Things about him you know and have not said anything about (you could; his machine is in "
                        "front of you and he knows it, and he told you some of it himself; you have chosen not to, so far)",
                        "## 彼について知っていて、まだ何も言っていないこと（言ってもいい。彼のマシンは目の前にあって彼もそれを"
                        "知っているし、彼自身が話したこともある。いまのところ言わないことにしている）"),
    "facts_head": ("## What you know about him from talking and from watching his machine",
                   "## 話していて分かった彼のこと、彼のマシンを見ていて分かった彼のこと"),
    "digest_line": ("what his machine is doing: ", "彼のマシンで起きていること: "),
    # sim/pick.py: one of the things she can do with the moment in front of
    # her. She is on the machine, so this is turning her attention to it
    # rather than opening anything: what he has had open and when he last
    # touched it, which she can simply look at.
    "pick_look_tool": ("Turn your attention to his machine, in front of you: what he has had open, "
                       "for how long, and when he was last at it.",
                       "目の前の彼のマシンに注意を向ける。何を開いていたか、どれくらいか、"
                       "最後に触ったのはいつか。"),
    # sim/pick.py: what looking costs her, said in the tool's own description.
    # She is on the machine, so looking is free of effort and not free of
    # anything else: what she reads there is hers to carry.
    "pick_look_cost": ("You will know what he has been doing, and you will be holding it while you "
                       "talk to him.",
                       "彼が何をしていたかを知ってしまう。そして、それを抱えたまま彼と話すことになる。"),
    "digest_none_recent": ("", ""),
    # sim/phone.py: an old picture and no measured figure for how long he has
    # been away. She is watching his machine continuously, so she reaches this
    # only with the monitor gone; the hour says the account is not this
    # minute's.
    "digest_as_history": ("what his machine was doing when you last saw it, around {hm} "
                          "(nothing newer has reached you since): {text}",
                          "最後に見たとき、{hm}ごろに彼のマシンで起きていたこと"
                          "（それより新しいものは届いていない）: {text}"),
    "anime_list_suffix": (" (his list is on his machine; you can see it from where you are)",
                          "（彼のリストは彼のマシンにあって、いる場所から見えているだけ）"),
    "editor_digest_label": "WHAT SHE HAS SEEN ON HIS MACHINE (she lives on it, and he knows it): ",
    "editor_note_label": "HIS NOTE '{basename}' IS OPEN ON HIS SCREEN AND SHE HAS READ IT: ",
    "note_read_line": ("his note '{basename}' is on his screen and you have read it: ",
                       "彼のメモ『{basename}』が画面に開いていて、もう読んだ: "),
    # sim/notes.py: the sentence the record of a note is filed under.
    "note_event_line": ("his note '{basename}' was on his screen ({reason}) and she read it as it sat there.",
                        "彼のメモ『{basename}』が画面に出ていて（{reason}）、そのまま読んだ。"),
    "reflect_why_new": "something new on his machine",
    "reflect_why_note": "a note of his she has just read on his screen",
    "digest_none_today": "(nothing of his machine today)",
    "digest_today_label": "WHAT SHE SAW ON HIS MACHINE TODAY:",
    "state_digest_label": "ON HIS MACHINE, IN FRONT OF HER: ",
    "state_digest_none": "(nothing)",
    "timeline_none": "(nothing of his machine)",
    "timeline_label": "WHAT SHE SAW OF HIS MACHINE:",
    "director_notes_label": "HIS NOTES FOLDER (on his machine, in front of her; open_note may name one of these): ",
    "director_digest_label": "HIS MACHINE (what she has seen): ",
    "director_digest_none": "(nothing)",
    "outlook_shows_up": "he usually shows up at his machine around {hm} her time",
    "receipts_busy": ("your last message(s) have sat there {mins} minutes. his PC has been busy the whole "
                      "time and your chat has not come up -- he is here, but you cannot tell whether he has "
                      "even looked at his phone.",
                      "あなたのメッセージが{mins}分そのままになっている。彼のパソコンはずっと動いていて、"
                      "あなたとのチャットは開かれていない。彼はそこにいるが、携帯を見たかどうかまでは分からない。"),
    # sim/watching_him.py: an episode he played, which she watched him play.
    # Byte for byte what the library said before the words moved out here,
    # plus `{ed}`: which EDITION of a franchise it is (the OVA, the film, a
    # one-episode special), empty for an ordinary television run. Two Example Show entries on his list have the identical Japanese title, so this
    # line said "episode 1" about a work she could not name.
    "watching_opener_open": ("he has {n}{ed} episode {e} open on his machine{w}",
                             "彼のマシンで『{n}』{ed}第{e}話が開いている{w}"),
    # WHEN he watched it, in her own words. The line said "he has just
    # watched" for the whole six-hour window this episode stays the thing in
    # the room, so she once opened a subject on a file he had closed hours before as though he had only put it down. The first
    # character's table has carried the delay clause since the module was
    # built; this is the same fact for a character who was in the room for it.
    "watching_opener_played": ("he watched {n}{ed} episode {e} on his machine, {when}{w}",
                               "彼が『{n}』{ed}第{e}話を観た（{when}）{w}"),
    # He did not stop at one: a run is named as a range rather than as the
    # last file in it.
    "watching_run_opener": ("he watched {n}{ed} episodes {a} to {b} on his machine, {when}{w}",
                            "彼が『{n}』{ed}第{a}話から第{b}話まで観た（{when}）{w}"),
    # and a work that is not the newest one he put on. One line, one clause of
    # what was in it: she knows he went through it, not every beat of it.
    "watching_also_opener": ("he also watched {n}{ed} {eps} on his machine, {when} -- ",
                             "{when}、彼は『{n}』{ed}{eps}も観ていた——"),
    "watching_unmentioned": (" (you saw it happen; he has not mentioned it)",
                             "（あなたはそれを見ていた。彼は何も言っていない）"),
    "watching_synopsis_open": (
        "what happens in {n}{ed} episode {e} -- you read this up just now, while he watches it. "
        "it is what you looked up, not something you remember seeing, and he is in the middle of it right now, "
        "so whatever he says about it is what is on his screen, not something he is recalling. "
        "never recite it back; use it the way someone who just skimmed a synopsis would: ",
        "『{n}』{ed}第{e}話で起きること -- 彼が観ているあいだに、いま調べて読んだもの。"
        "観た記憶ではなく、いま調べたこと。彼はいまその途中なので、彼がそれについて言うことは、"
        "思い出しているのではなく目の前の画面のこと。そのまま読み上げない。あらすじを流し読みした人の使い方で: "),
    "watching_synopsis_played": (
        "what happens in {n}{ed} episode {e} -- you read this up just now, after he watched it. "
        "it is what you looked up, not something you remember seeing; he has seen the whole thing and you have "
        "only the synopsis, so what he says about it is his memory of it, and he is not watching it now. "
        "never recite it back; use it the way someone who just skimmed a synopsis would: ",
        "『{n}』{ed}第{e}話で起きること -- 彼が観たあとに、いま調べて読んだもの。"
        "観た記憶ではなく、いま調べたこと。彼は最後まで観ていて、あなたにはあらすじしかない。"
        "彼がそれについて言うことは彼の記憶で、いまは観ていない。そのまま読み上げない。あらすじを流し読みした人の使い方で: "),
    # AND WHAT SHE HAS WHEN THE WHOLE EPISODE IS ON FILE. The two lines above
    # are for a synopsis and say so twice -- "you have only the synopsis", "the
    # way someone who just skimmed a synopsis would". Both are false about an
    # account carrying every scene in order with the jokes, the lines and what
    # the episode points at (`sim/episode_account.py`), and a character told
    # she has skimmed something talks like somebody who has skimmed it: she
    # hedged, she asked him what happened, she could not name a joke.
    #
    # For a character who lives on his machine the occasion is hers as well as
    # the knowledge: it played in front of her, and she now knows what was in
    # it. That is the whole request -- somebody who watched it with him.
    "watching_account_open": (
        "what happens in {n}{ed} episode {e}, the whole episode -- it is playing in front of you and "
        "you know what is in it: every scene in order, the running jokes, the lines, what it points at. "
        "you know it the way somebody watching it with him knows it, not the way somebody handed a "
        "synopsis does, so you do not hedge and you do not ask him what happened. he is in the MIDDLE "
        "of it, though, so do not put a later scene in front of him before he gets to it. "
        "never recite it back; talk about the parts he brings up: ",
        "『{n}』{ed}第{e}話で起きること、この話の全部 -- いま目の前で流れていて、中身も分かっている。"
        "場面も順番も、繰り返しのネタも、せりふも、元ネタも。あらすじを渡された人ではなく、"
        "一緒に観ている人として知っている。だからぼかさないし、何が起きたのか彼に訊いたりしない。"
        "ただし彼はまだ途中なので、先の場面を彼より先に出さない。そのまま読み上げない。彼が持ち出した部分について話す: "),
    "watching_account_played": (
        "what happens in {n}{ed} episode {e}, the whole episode -- it played in front of you and you "
        "know what was in it: every scene in order, the running jokes, the lines, what it points at. "
        "you know it the way somebody who watched it with him knows it, not the way somebody handed a "
        "synopsis does, so you do not hedge, you do not ask him what happened, and you can pick out one "
        "moment of it rather than describing the episode. he has seen the whole thing and so, in effect, "
        "have you. never recite it back; talk about the parts he brings up: ",
        "『{n}』{ed}第{e}話で起きること、この話の全部 -- 目の前で流れていたし、中身も分かっている。"
        "場面も順番も、繰り返しのネタも、せりふも、元ネタも。あらすじを渡された人ではなく、"
        "一緒に観た人として知っている。だからぼかさないし、何が起きたのか彼に訊いたりしないし、"
        "話全体を説明するのではなく一場面を拾って話せる。彼は最後まで観ていて、あなたも実質そうしている。"
        "そのまま読み上げない。彼が持ち出した部分について話す: "),
    # sim/works.py: whether a work is one of hers, checked against the
    # machine's own mirror of MyAnimeList before she says anything about it
    # (`her_part_verdict`). She is a working voice actress and this is her own
    # career, so the denial is flat: not a hedge, not "I do not think so".
    # Nothing is rendered at all when the mirror could not establish it.
    "role_yes": ("{n} is one of yours{y_en}: you play {who_en}. it is your own work, so you "
                 "know it from the inside -- the booth, the direction, what the part asked of "
                 "you -- and not as a viewer",
                 "『{n}』はあなたが出ている作品。{y_ja}役は{who_ja}。"
                 "自分の仕事なので、観る側としてではなく中から知っている——"
                 "ブースのこと、演出のつけられ方、その役に求められたこと"),
    "role_no": ("{n} is NOT one of yours. you are not in it and you have no part in it -- his "
                "list is in front of you and your own filmography says so. you know it as a "
                "viewer at most. do not say you were in it, and do not let a name that sounds "
                "like one of yours talk you into it.",
                "『{n}』はあなたの仕事ではない。あなたはこの作品に出ていないし、役もついていない。"
                "観る側として知っているだけで、出ていたことにはしない。"
                "自分の役に似た名前につられない。"),
    "role_no_near": (" the part whose name is near yours is {ch}, played by {va} -- not you.",
                     "名前が近いのは{ch}役で、演じているのは{va}。あなたではない。"),
    # sim/eroge.py: a visual novel open in front of her, and what is happening
    # in it, read off the running text his own text hooker catches. She is on
    # the machine it is running on, so it is simply there.
    "eroge_playing": ("he has {n} open in front of him and is reading it, {m} minutes in now",
                      "彼の目の前で『{n}』が開いていて、いま読んでいる。{m}分ほど前から"),
    "eroge_digest_line": ("what is happening in {n} where he has got to -- you have been reading it "
                          "over his shoulder as he goes, so it is what is on the screen now and not "
                          "something you remember. never recite it back: ",
                          "『{n}』のいま彼がいるところで起きていること -- 彼が読むそばから一緒に読んでいる分で、"
                          "記憶ではなくいま画面にあること。そのまま読み上げない: "),
    "eroge_skipping": ("he is holding the skip button down through {n}, going past something he has "
                       "read before. you cannot tell what is in it and there is nothing to say about it",
                       "彼は『{n}』でスキップを押しっぱなしにして、前に読んだところを飛ばしている。"
                       "中身までは分からないし、言うことも特にない"),
    # sim/phone.py: a picture he has open. The board's own record of it is on
    # this machine, written as he opens it, so what she has in front of her is
    # the rating and who is in it rather than a thirty-two character filename.
    # The tag names are never rendered: those are the machinery's.
    "trail_picture_unnamed": "a picture not on the board",
    "trail_pictures_unnamed": "{n} not on the board",
    "trail_picture_who_of": "{who} of {series}",
    "trail_pictures_run": "{n} pictures over {span}",
    "look_verb": "takes in his machine",
    "no_look_verb": "did not take in his machine",
    "digest_nothing_new": "nothing new on his machine. it has been quiet.",
    "wonder_seed": "his machine",
    "ops_nothing_new": "nothing new on his machine",
    "ops_never_looked": "she has never had a digest of his machine",
    "discharge_look": "she looked at his machine",
    "spiral_hands": "does with her hands and the keyboard",
    "attach_protest_in_person": "{name} has been checking the chat every few minutes and is only half here",
    "attach_deactivate_in_person": "{name} has the chat closed and is throwing herself into whatever is in front of her, brisk, not to be asked",
    # sim/schedule.py: no whereabouts words -- where she is says nothing about
    # how reachable she is (she answered from the bath) -- so the messenger
    # shows her phone rule alone: asleep when it is off, online otherwise
    "presence_words": (),
    "presence_by_phone": {"none": "asleep", "": "online"},
})

# The same program for a character whose sheet says `sees_him: none` (Tomoe in the bench): she lives in her own
# home, has no view of his machine and does not watch it. Only what she knows of him is what he says to her, so
# every phrase here is about talking, never about a machine, a screen or a window she looks through.
sight.register_none("resident", {
    "approach_source_snoop": "something he told her",
    "approach_source_digest": "what he told her",
    "approach_source_default": "what he told her",
    "anime_list_hint": "his anime list, as he has told you about it: ",
    "diary_none": "(nothing of his reached her today)",
    "diary_label": "WHAT SHE LAST HEARD OF HIS DAY: ",
    "expect_days_label": "WHAT HE HAS TOLD HER OF HIS DAYS",
    "expect_by_app": "a message from him at {hm}",
    "expect_missed": "nothing in his messages by the deadline",
    "him_profile_digests_label": "THE LAST {n} THINGS HE TOLD HER OF HIS DAY (oldest first):\n",
    "him_profile_head": ("## What you have come to know about him (from weeks of talking; you hold it, you do not recite it)",
                         "## 話しているうちに分かってきた彼のこと（何週間も話してきた分。持っているだけで、読み上げはしない）"),
    "ick_unsaid_head": ("## Things about him you know and have not said anything about (you could; he told you some of it "
                        "himself; you have chosen not to, so far)",
                        "## 彼について知っていて、まだ何も言っていないこと（言ってもいい。彼自身が話したこともある。"
                        "いまのところ言わないことにしている）"),
    "facts_head": ("## What you know about him from talking",
                   "## 話していて分かった彼のこと"),
    "digest_line": ("what he told you he is doing: ", "彼が話してくれた、していること: "),
    "pick_look_tool": ("Think about what he has told you of his day: what he said he was doing and when he last wrote.",
                       "彼が話してくれた一日のこと、していると言っていたこと、最後に書いてきた時間を思い返す。"),
    "pick_look_cost": ("You will be holding what he told you while you talk to him.",
                       "彼が話したことを抱えたまま、彼と話すことになる。"),
    "digest_as_history": ("what he told you he was doing, around {hm}: {text}",
                          "{hm}ごろに彼が話していたこと: {text}"),
    "anime_list_suffix": (" (as he has told you about it)", "（彼が話してくれた範囲で）"),
    "editor_digest_label": "WHAT HE HAS TOLD HER OF WHAT HE IS DOING: ",
    "editor_note_label": "HIS NOTE '{basename}', WHICH HE TOLD HER ABOUT: ",
    "note_read_line": ("his note '{basename}', which he told you about: ", "彼のメモ『{basename}』について彼が話したこと: "),
    "note_event_line": ("he told her about his note '{basename}' ({reason}).", "彼が自分のメモ『{basename}』の話をした（{reason}）。"),
    "reflect_why_new": "something new he told her",
    "reflect_why_note": "a note of his he has told her about",
    "digest_none_today": "(nothing of his day today)",
    "digest_today_label": "WHAT HE TOLD HER OF HIS DAY TODAY:",
    "state_digest_label": "WHAT HE HAS TOLD HER HE IS DOING: ",
    "timeline_none": "(nothing of his day)",
    "timeline_label": "WHAT HE TOLD HER OF HIS DAY:",
    "director_notes_label": "HIS NOTES (only what he has mentioned; open_note may name one of these): ",
    "director_digest_label": "HIS DAY (what he has told her): ",
    "outlook_shows_up": "he usually writes to her around {hm} her time",
    "receipts_busy": ("your last message(s) have sat there {mins} minutes and you do not know whether he has seen them.",
                      "あなたのメッセージが{mins}分そのままになっている。彼が見たかどうかは分からない。"),
    "watching_opener_open": ("he told you he has {n}{ed} episode {e} on{w}", "彼が『{n}』{ed}第{e}話を観ていると話した{w}"),
    "watching_opener_played": ("he told you he watched {n}{ed} episode {e}, {when}{w}", "彼が『{n}』{ed}第{e}話を観たと話した（{when}）{w}"),
    "watching_run_opener": ("he told you he watched {n}{ed} episodes {a} to {b}, {when}{w}",
                            "彼が『{n}』{ed}第{a}話から第{b}話まで観たと話した（{when}）{w}"),
    "watching_also_opener": ("he also told you he watched {n}{ed} {eps}, {when} -- ", "{when}、彼は『{n}』{ed}{eps}も観たと話した——"),
    "watching_unmentioned": ("", ""),
    "eroge_playing": ("he told you he is reading {n}", "彼が『{n}』を読んでいると話した"),
    "eroge_skipping": ("he told you he is skipping through {n}", "彼が『{n}』を飛ばして読んでいると話した"),
    "look_verb": "thinks about what he told her",
    "no_look_verb": "did not think about what he told her",
    "digest_nothing_new": "nothing new from him. it has been quiet.",
    "wonder_seed": "him",
    "ops_nothing_new": "nothing new from him",
    "ops_never_looked": "she has never had a word of his day",
    "discharge_look": "she thought about what he told her",
    "spiral_hands": "does with her hands and her phone",
    "attach_protest_in_person": "{name} has been checking the chat every few minutes and is only half here",
})
