"""Chapter 13: the keypad tones, and what does and does not read them."""

import numpy as np
import pytest

import dtmf
from voicelab.audio import mulaw_roundtrip, read_wav, write_wav

KEYPAD = "123A456B789C*0#D"


def test_every_key_on_the_pad_survives_make_and_decode(tmp_path):
    path = str(tmp_path / "all.wav")
    dtmf.make(KEYPAD, path)
    assert "".join(dtmf.decode(path)) == KEYPAD


def test_a_key_is_the_two_tones_q23_names(tmp_path):
    """Not "sounds a bit like": exactly the pair, and nothing else."""
    path = str(tmp_path / "five.wav")
    dtmf.make("5", path)
    pcm, rate = read_wav(path)
    block = pcm[: int(0.02 * rate)]
    energy = {f: dtmf.goertzel(block, rate, f)
              for f in dtmf.LOW + dtmf.HIGH}
    assert dtmf.pair_for("5") == (770, 1336)
    # Ten times its nearest rival, not a thousand. A 20 ms block at
    # 8 kHz resolves to 50 Hz bins and the rows are 73 Hz apart, so
    # the losers are never silent. That narrow margin is the whole
    # reason the dominance guard below is delicate to set.
    for row in dtmf.LOW:
        if row != 770:
            assert energy[770] > 10 * energy[row]
    for col in dtmf.HIGH:
        if col != 1336:
            assert energy[1336] > 10 * energy[col]


def test_the_telephone_codec_costs_the_tones_nothing(tmp_path):
    """Chapter 2 found G.711 cost its transcriber nothing either.

    What the telephone band costs is the top and bottom of a voice,
    which a listener hears. The keys were designed to sit in what is
    left, so the roundtrip should not move a single one.
    """
    clean = str(tmp_path / "clean.wav")
    down_the_line = str(tmp_path / "phone.wav")
    dtmf.make("4721885309", clean)
    pcm, rate = read_wav(clean)
    write_wav(down_the_line, mulaw_roundtrip(pcm), rate)
    assert dtmf.decode(down_the_line) == dtmf.decode(clean)
    assert "".join(dtmf.decode(down_the_line)) == "4721885309"


def test_silence_is_not_a_keypress(tmp_path):
    path = str(tmp_path / "quiet.wav")
    write_wav(path, np.zeros(dtmf.RATE, dtype=np.int16), dtmf.RATE)
    assert dtmf.decode(path) == []


def test_a_voice_reads_as_keys_unless_the_winner_has_to_dominate():
    """The mirror of the speech model's silence, and the guard for it.

    Without a dominance check the decoder names a key for every loud
    block, so a spoken sentence comes out as a long string of digits
    that nobody typed. This is the failure the chapter is really about,
    so it is asserted in both directions.
    """
    speech = "audio/ch09/plain.wav"
    loose = dtmf.decode(speech)
    strict = dtmf.decode(speech, dtmf.DOMINANCE)
    assert len(loose) > 50, "the flaw this test exists to pin down"
    assert strict == []


def test_the_guard_does_not_cost_us_real_keys(tmp_path):
    path = str(tmp_path / "keys.wav")
    dtmf.make(KEYPAD, path)
    assert "".join(dtmf.decode(path, dtmf.DOMINANCE)) == KEYPAD


def test_a_key_that_is_not_on_a_telephone_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        dtmf.make("Z", str(tmp_path / "nope.wav"))


def test_the_guard_has_a_narrow_window(tmp_path):
    """Too high and a real key is reported twice, not missed.

    Blocks in the middle of a held key fail a strict test, which
    resets the decoder's "same key as last time" memory, so the key
    is recorded again when the next good block arrives. The keys are
    correct up to 10 and break at 11, so the whole working range
    above the chosen 8 is two integers wide.
    """
    path = str(tmp_path / "long.wav")
    dtmf.make("4721885309", path)
    assert "".join(dtmf.decode(path, dtmf.DOMINANCE)) == "4721885309"
    assert "".join(dtmf.decode(path, 10.0)) == "4721885309"
    assert "".join(dtmf.decode(path, 11.0)) == "447218855309"


def test_only_the_770_hz_row_breaks(tmp_path):
    """The break is my measurement, not the keypress.

    A 20 ms block at 8 kHz resolves to 50 Hz steps, and goertzel
    snaps each candidate to the nearest one. 770 Hz lands on 750,
    twenty hertz out. That is not the largest error in absolute terms
    (1477 Hz is 23 Hz out) but it is the largest compared with how
    close its neighbours are, and a neighbour is what it has to beat.
    So 770 leaks into the 700 Hz bin and never leads by much, and the
    keys on that row, 4, 5, 6 and B, are exactly the ones that double.
    """
    path = str(tmp_path / "pad.wav")
    dtmf.make(KEYPAD, path)
    broke = "".join(dtmf.decode(path, 11.0))
    assert broke == "123A44556BBB789C*0#D"
    for key in "123A789C*0#D":  # every key NOT on the 770 Hz row
        assert broke.count(key) == 1

    def crowding(freq: int, group: tuple[int, ...]) -> float:
        """Binning error as a fraction of the gap to the neighbour."""
        bin_hz = int(0.5 + 160 * freq / 8000) * 8000 / 160
        gap = min(abs(freq - f) for f in group if f != freq)
        return abs(bin_hz - freq) / gap

    worst = max(dtmf.LOW, key=lambda f: crowding(f, dtmf.LOW))
    assert worst == 770
    assert crowding(770, dtmf.LOW) > max(
        crowding(f, dtmf.HIGH) for f in dtmf.HIGH)


def test_the_guard_does_not_generalise_to_other_recordings():
    """The number 8 fits one file. It does not fit the book's own.

    audio/refund_question.wav is the question every caller run since
    Chapter 4 has played. At the dominance that silences plain.wav it
    still reports five keys nobody typed, and it does not go quiet
    until 31, by which point the real keys are long destroyed. There
    is no value of this constant that does both jobs.
    """
    assert dtmf.decode("audio/ch09/plain.wav", dtmf.DOMINANCE) == []
    phantom = dtmf.decode("audio/refund_question.wav", dtmf.DOMINANCE)
    assert "".join(phantom) == "12*11"
    assert dtmf.decode("audio/refund_question.wav", 20.0) != []
