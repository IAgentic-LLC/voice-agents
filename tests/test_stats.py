from voicelab.stats import bootstrap_median_interval, wilson_interval


def test_wilson_matches_book_four():
    low, high = wilson_interval(6, 6)
    assert round(low, 4) == 0.6097 and high == 1.0


def test_wilson_ten_of_ten():
    low, _ = wilson_interval(10, 10)
    assert round(low, 4) == 0.7225


def test_bootstrap_is_reproducible_and_brackets_median():
    values = [0.72, 0.72, 0.73, 0.78, 0.80, 0.81, 2.09, 2.17, 2.19, 2.30]
    first = bootstrap_median_interval(values)
    assert first == bootstrap_median_interval(values)
    assert first[0] <= 0.805 <= first[1]
