"""What the runtime may ask of a channel, and what a channel need not do.

The runtime talks to her chat through one object, `App.tg`, and the channels
are the visual novel (`vn_bot.py`, the stage this fork runs on), TALKAPP
(`talkapp_bot.py`, a phone hub), and Telegram (`telegram_bot.py`, kept only as
the console dry-run sink and the fallback for a config with no other channel).
They share the nine methods every message needs, and the richer channels have
more -- a photo, a sticker, a voice note attached to a bubble, the lines he
tapped to hear, the ops commands -- which the runtime used to ask for with
`hasattr` in six places, and got one signature wrong (a voice note with
`attach_to` on a channel whose `send_voice` took none). Here the extras are
methods that do nothing, and every channel has them: a channel that cannot
send a photo says so by returning False, and the runtime reads the answer
instead of the type.

The wires (`sim/wiring.py`) are declared here for all of them: the social
graph for the backstage view, the ops view, and her face for the app's header.
A channel with nowhere to show them leaves them unread.
"""


class Channel:
    # Whether a message id from this channel is unique for good. Telegram
    # assigns a hub message id that never repeats, so the store may use `tg_id`
    # to throw away a redelivery of a message it already has (`store.py`,
    # `add_message`; the 2026-08-19 double-answer after five restarts). The VN
    # stage and TALKAPP hand out ids from a counter that starts at 1 in every
    # process (`channels/vn_bot.py`), so the same number means a different line
    # after a restart and the store must not compare it. This is a property of
    # the channel, not a rule of the store.
    MSG_ID_UNIQUE = False

    WIRES = ('graph', 'ops_provider', 'reaction_provider', 'voice_model_provider',
             'voice_model_setter', 'scene_provider', 'emotion_provider',
             'present_notice', 'speak_now', 'stage_model_provider', 'stage_model_setter',
             'stage_chat', 'stage_history', 'stage_snapshot', 'gauge_nudge',)

    def send_photo(self, path):
        """A photo of hers before the bubbles that caption it. False: it did
        not go, and the delivery says so."""
        return False

    def send_sticker(self, path, bucket="", ts=None, quiet=False, auto=False):
        """A reaction of hers, a frame of her the size of a sticker."""
        return False

    def send_voice(self, ogg_path, attach_to=0):
        """A voice note; `attach_to` names the bubble it belongs to, and a
        channel with no notion of that ignores it."""
        return False

    def voice_url(self, ogg_path):
        """The URL for a clip already on disk, with nothing filed against a
        turn. The backlog's replay uses this; a channel with no stage answers
        ''."""
        return ""

    def send_audio(self, audio_path):
        return False

    def speak_requests(self):
        """Lines he has tapped to hear her say: [{id, text}]."""
        return []

    def get_ops_commands(self):
        """Operator commands typed into the app's ops view."""
        return []

    def post_ops_result(self, cmd, text):
        return None

    def peer_send(self, to_id, text):
        """Hand a message to another character, by her hub id. Returns the
        channel's own id for it, or False. A channel with no other characters
        on it says so here."""
        return False

    def peer_updates(self, after=0):
        """What other characters have said to her since `after`:
        [{id, from, name, text, ts}]. The cursor is the caller's."""
        return []
