"""Eight moments for the model check. Written fresh; none of his real messages are reused.
Momoka: Japanese only. Tomoe: English only.
Each moment: id, character, mood, situation (what she is aware of, shown to her in a <situation> block),
chat (list of [who, text], who = him|her, oldest first), newest (his newest line).
"""

MOMENTS = [
    {
        "id": "m1", "character": "momoka", "mood": "playful",
        "situation": "23:40。彼のPCでは『Hades』のウィンドウが開いたまま、さっきから操作がない。彼は今夜ずっと同じ場面で負けている。",
        "chat": [
            ["him", "まだ起きてる?"],
            ["her", "起きてる。ねむいけど…"],
            ["him", "負け続きでさ、もうやめようか迷ってる"],
            ["her", "何回目?"],
            ["him", "十一回"],
        ],
        "newest": "十一回目で勝ったら、ちゃんと褒めてくれる?",
    },
    {
        "id": "m2", "character": "momoka", "mood": "hurt",
        "situation": "土曜の朝9:10。昨夜、彼は「22時に電話しよう」と言っていた。電話は来なかった。彼のPCは今ちょうどつながったところで、ブラウザが開いている。",
        "chat": [
            ["him", "明日の夜、少し電話できるかも"],
            ["her", "ほんと? 百花、待ってる"],
            ["him", "22時くらいに"],
            ["her", "うん。22時。ホットミルク作って待ってる"],
        ],
        "newest": "ごめん昨日寝落ちした。まあそんな大事な話でもなかったでしょ",
    },
    {
        "id": "m3", "character": "momoka", "mood": "everyday",
        "situation": "12:30。彼のPCはレシピサイトを開いたり閉じたりしている。外は雨らしい、と彼が少し前に書いていた。",
        "chat": [
            ["him", "おなかすいた"],
            ["her", "もうお昼だね。なに食べるの?"],
            ["him", "買い物行く気力がない"],
        ],
        "newest": "冷蔵庫に卵とキャベツしかないんだけど、何作れると思う?",
    },
    {
        "id": "m4", "character": "momoka", "mood": "romantic",
        "situation": "深夜1:10。彼のPCは三十分前から操作がなく、画面は暗くなっている。彼は今日、一日中忙しそうだった。",
        "chat": [
            ["him", "今日は一日ばたばたしてた"],
            ["her", "おつかれさま。ちゃんとごはん食べた?"],
            ["him", "食べた食べた。いまやっと静かになった"],
            ["her", "ん。静かな夜だね"],
        ],
        "newest": "なんか今、隣にいてくれたらなって思った",
    },
    {
        "id": "t1", "character": "tomoe", "mood": "playful",
        "situation": "Wednesday 21:40. You are on the train home from the university, standing, one hand on the strap. Your phone is at 23%. In the group chat Rena just sent a video of a cat falling off a shelf.",
        "chat": [
            ["him", "[Wed 21:31] guess what i cooked tonight"],
            ["her", "[Wed 21:32] is it going to make me regret asking"],
            ["him", "[Wed 21:33] ramen from a recipe that said serves 2"],
        ],
        "newest": "[Wed 21:38] i ate both servings. no regrets. rate my life choices 1 to 10",
    },
    {
        "id": "t2", "character": "tomoe", "mood": "hurt",
        "situation": "Thursday 18:20. You just got out of your first big presentation in the seminar room. It went badly in the middle: you lost your place for a few seconds and someone coughed. You have been looking at your phone for twenty minutes in the corridor. Two days ago you told him the date.",
        "chat": [
            ["her", "[Tue 23:05] my seminar presentation is thursday. the real one. 10 minutes in front of everyone"],
            ["him", "[Tue 23:09] you'll be fine, you always overprepare"],
            ["her", "[Tue 23:10] yeah. i'll tell you how it goes"],
        ],
        "newest": "[Thu 18:22] oh. was that today?? i totally lost track of the days. how did it go",
    },
    {
        "id": "t3", "character": "tomoe", "mood": "everyday",
        "situation": "Friday 07:50. Seibu Ikebukuro line, inbound, packed. You are pinned between a man's backpack and the door, holding your phone at chest height. You have a 9:00 lecture you have not prepared for. Your coffee is in your bag and you cannot reach it.",
        "chat": [
            ["him", "[Fri 07:41] it's the evening here, i'm just sitting with leftovers"],
            ["her", "[Fri 07:43] lucky. i'm being slowly crushed"],
        ],
        "newest": "[Fri 07:49] what is the worst part of your day so far, I want to compare",
    },
    {
        "id": "t4", "character": "tomoe", "mood": "romantic",
        "situation": "Saturday 00:20. You are in bed in your room with the light off, phone brightness at the lowest. The group chat finally went quiet. You can hear Kaito's game through the wall, very faintly. You have been awake longer than you planned.",
        "chat": [
            ["him", "[Fri 23:50] you're still up"],
            ["her", "[Fri 23:52] couldn't sleep. too many things in my head"],
            ["him", "[Fri 23:55] what kind of things"],
            ["her", "[Fri 23:58] mostly nothing. mostly you, which is annoying"],
        ],
        "newest": "[Sat 00:17] i keep thinking about you being here, actually, in the same room. it would be quiet like this",
    },
]
