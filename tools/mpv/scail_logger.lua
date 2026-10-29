-- What he is playing, written from inside the player.
--
-- Three records, and each answers a different question.
--
--   * `mpv_history.log`, one `epoch|path` line the moment a file opens: that
--     an episode happened at all. Unchanged; two readers depend on it.
--   * `mpv_now.json`, refreshed while a file is open: where he is in it RIGHT
--     NOW. Elapsed wall clock since the file opened cannot answer that,
--     because he pauses -- and pausing is exactly the moment worth knowing
--     about. mpv knows, so mpv is asked: `time-pos` and `pause` come from the
--     player itself, and a paused file simply stops moving while the state
--     file keeps saying so.
--   * `mpv_plays.log`, one line when a file ENDS: how much of it he actually
--     sat through. Without it nobody can tell a full watch from a skim -- the
--     open line is identical either way -- and the old 2023 logger recorded
--     the exit position for exactly this reason.
--
-- The number that separates a watch from a skim is `watched=`: wall-clock
-- seconds accumulated while the file was playing and NOT paused. The end
-- position alone cannot do it, because seeking to the last minute and closing
-- the file gives the same `time=` as sitting through the whole thing.
--
-- The play line, one per finished play, appended:
--
--   <open epoch>|<end epoch>|<path>|length=<s>|time=<s>|watched=<s>|reason=<r>
--
-- `open epoch` is the same integer the history line carries for that open,
-- which is what joins the two records. `reason` is mpv's own end-file reason:
-- eof (it ran out), stop (he closed the file), quit (he closed the player),
-- error, redirect, unknown. mpv reports `time-pos` as nil once a file has hit
-- its end, so the last position observed while it played is what is written,
-- and an `eof` end is recorded at the full length.
--
-- Install: copy to %APPDATA%\mpv\scripts\scail_logger.lua. Read by
-- sim/watching_him.py and machine/plays.py; spec PROJECT.md §12.12.

local mp = require 'mp'
local os = require 'os'

local TICK = 10          -- seconds between refreshes of the state file
local SAMPLE = 1         -- seconds between samples of position and pause
local appdata = os.getenv("APPDATA")

-- The play in front of him, or nil between files. Everything about the
-- current play hangs off this one table, so "is a play open" and "has its
-- line been written" are the same question and the line cannot be written
-- twice: mpv fires end-file AND shutdown when he closes the player.
local play = nil
local timer = nil
local since_write = 0

local function path_of(name)
    if not appdata then return nil end
    return appdata .. "\\mpv\\" .. name
end

local function append(name, line)
    local p = path_of(name)
    if not p then return end
    local f = io.open(p, "a")
    if f then
        f:write(line .. "\n")
        f:close()
    end
end

-- A tiny JSON writer rather than mp.utils.format_json: the fields are known,
-- and the only string is a Windows path, whose backslashes and quotes are the
-- one thing that has to be escaped properly.
local function quote(s)
    s = tostring(s or ""):gsub("\\", "\\\\"):gsub('"', '\\"')
    return '"' .. s .. '"'
end

local function num(v)
    if type(v) ~= "number" then return "null" end
    return string.format("%.1f", v)
end

local function fixed(v)
    return string.format("%.1f", type(v) == "number" and v or 0)
end

-- Wall clock spent unpaused, taken in samples rather than as one span from
-- the open, because a file paused for an hour is not an hour watched. A gap
-- much longer than a sample is the machine having been suspended or the
-- script having been starved, and counting it would hand a sleeping machine
-- a full watch, so it is credited at one sample and no more.
local function accrue()
    local t = mp.get_time()
    if play and play.mark then
        local d = t - play.mark
        if d > 0 then
            if d > SAMPLE * 3 then d = SAMPLE end
            if not play.paused then play.watched = play.watched + d end
        end
    end
    if play then play.mark = t end
end

local function write_now(playing)
    local p = path_of("mpv_now.json")
    if not p then return end
    local body
    if playing and play then
        body = string.format(
            '{"t":%d,"playing":true,"path":%s,"pos":%s,"dur":%s,"paused":%s,"watched":%s,"opened":%d}',
            os.time(), quote(play.path),
            num(mp.get_property_number("time-pos") or play.pos),
            num(mp.get_property_number("duration") or play.dur),
            tostring(play.paused and true or false),
            num(play.watched), play.opened)
    else
        body = string.format('{"t":%d,"playing":false}', os.time())
    end
    local f = io.open(p, "w")
    if f then
        f:write(body)
        f:close()
    end
end

-- one sample: the position and the length as mpv has them now, the unpaused
-- seconds so far, and the state file every TICK
local function sample()
    if not play then return end
    accrue()
    local pos = mp.get_property_number("time-pos")
    if type(pos) == "number" then play.pos = pos end
    local dur = mp.get_property_number("duration")
    if type(dur) == "number" and dur > 0 then play.dur = dur end
    since_write = since_write + SAMPLE
    if since_write >= TICK then
        since_write = 0
        write_now(true)
    end
end

local function stop_ticking()
    if timer then timer:kill(); timer = nil end
end

local function start_ticking()
    stop_ticking()
    since_write = 0
    timer = mp.add_periodic_timer(SAMPLE, sample)
end

-- The end of one play, whatever ended it. `reason` is mpv's own word for it
-- where there is an event to read it off, and "quit" when the player is going
-- down without one.
local function finish(reason)
    if not play then return end
    accrue()
    local pos = mp.get_property_number("time-pos")
    if type(pos) == "number" then play.pos = pos end
    -- mpv has no position left to report once a file has run out, and the
    -- honest answer for a file that reached its end is its whole length
    if reason == "eof" and type(play.dur) == "number" and play.dur > 0 then
        play.pos = play.dur
    end
    append("mpv_plays.log", string.format(
        "%d|%d|%s|length=%s|time=%s|watched=%s|reason=%s",
        play.opened, os.time(), play.path,
        fixed(play.dur), fixed(play.pos), fixed(play.watched),
        tostring(reason or "unknown")))
    play = nil
end

mp.register_event("file-loaded", function()
    local path = mp.get_property("path")
    if not path then return end
    -- a file opening while another is still open (the playlist stepping on)
    -- ends that one first, so every open has exactly one play line
    finish("stop")
    local opened = os.time()
    play = {path = path, opened = opened, watched = 0.0, mark = mp.get_time(),
            paused = mp.get_property_bool("pause") and true or false,
            pos = mp.get_property_number("time-pos") or 0.0,
            dur = mp.get_property_number("duration") or 0.0}
    append("mpv_history.log", opened .. "|" .. path)
    write_now(true)
    start_ticking()
end)

-- the moment he pauses is worth writing at once rather than up to a tick
-- later; the same observer covers him resuming, and the seconds so far are
-- banked against the state he was in until now
mp.observe_property("pause", "bool", function(_, value)
    if not play then return end
    accrue()
    play.paused = value and true or false
    since_write = 0
    write_now(true)
end)

mp.register_event("end-file", function(ev)
    stop_ticking()
    finish(ev and ev.reason or "unknown")
    write_now(false)
end)

mp.register_event("shutdown", function()
    stop_ticking()
    finish("quit")
    write_now(false)
end)
