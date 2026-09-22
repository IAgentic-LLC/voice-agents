"""The recorded question every caller plays, and where its speech ends.

The recording is 6.775 s long, but the last loud word ends at 6.000 s; the
rest is quiet room tone. Time to first audio is measured from the end of the
speech, not the end of the file.
"""

import wave

import numpy as np

QUESTION = "audio/refund_question.wav"
AUDIBLE_RMS = 300  # int16 loudness above this counts as speech


def read_question(path: str = QUESTION) -> tuple[int, np.ndarray]:
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        return w.getframerate(), pcm


def speech_end_s(path: str = QUESTION) -> float:
    """Seconds from the start of the file to the end of its last loud
    10 ms frame."""
    rate, pcm = read_question(path)
    step = rate // 100
    last = 0
    for i in range(0, len(pcm), step):
        chunk = pcm[i : i + step].astype(np.float64)
        if np.sqrt(np.mean(chunk**2)) > AUDIBLE_RMS:
            last = i + step
    return last / rate


SPEECH_END_S = speech_end_s()


def wait_from_speech_end(call: dict) -> float:
    """Time to first audio from the end of speech, for any recorded call.

    Calls recorded before this definition was fixed measured from the end
    of the file. Their question_s says when the file finished relative to
    the first frame, so the difference is known exactly.
    """
    if call.get("t0") == "speech_end" or call.get("source") == "browser":
        return call["ttfa_s"]
    return call["ttfa_s"] + call["question_s"] - SPEECH_END_S


def speech_end_wall(call: dict, listen_s: float) -> float:
    """Wall-clock time the caller stopped speaking, for any recorded call.
    Older calls stored the end of the file, or only when their record was
    written (listen_s after the end of the file)."""
    if call.get("t0") == "speech_end":
        return call["speech_end_wall"]
    file_end = call.get("speech_end_wall", call["t"] - listen_s)
    return file_end - (call["question_s"] - SPEECH_END_S)
