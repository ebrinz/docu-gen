"""Tests for numberwords module."""
import pytest
from docugen.numberwords import numbers_to_words, _int_to_words, _year_to_words


class TestIntToWords:
    def test_zero(self):
        assert _int_to_words(0) == "zero"

    def test_single_digit(self):
        assert _int_to_words(7) == "seven"

    def test_teens(self):
        assert _int_to_words(15) == "fifteen"

    def test_tens(self):
        assert _int_to_words(42) == "forty-two"

    def test_hundreds(self):
        assert _int_to_words(112) == "one hundred twelve"

    def test_thousands(self):
        assert _int_to_words(2000) == "two thousand"

    def test_large_comma_number(self):
        assert _int_to_words(64659) == "sixty-four thousand six hundred fifty-nine"

    def test_millions(self):
        assert _int_to_words(1000000) == "one million"


class TestYearToWords:
    def test_2017(self):
        assert _year_to_words(2017) == "twenty seventeen"

    def test_2000(self):
        assert _year_to_words(2000) == "two thousand"

    def test_2030(self):
        assert _year_to_words(2030) == "twenty thirty"

    def test_1999(self):
        assert _year_to_words(1999) == "nineteen ninety-nine"


class TestNumbersToWords:
    def test_dollar_amounts(self):
        result = numbers_to_words("$420 billion")
        assert "four hundred twenty billion dollars" in result

    def test_percentages(self):
        result = numbers_to_words("15 percent")
        assert "fifteen percent" in result

    def test_signed_percentages(self):
        result = numbers_to_words("+15.1%")
        assert "plus fifteen point one percent" in result

    def test_comma_numbers(self):
        result = numbers_to_words("64,659 compounds")
        assert "sixty-four thousand six hundred fifty-nine compounds" in result

    def test_decimals(self):
        result = numbers_to_words("Tanimoto 0.7")
        assert "zero point seven" in result

    def test_compound_names_preserved(self):
        result = numbers_to_words("PI-103 scored well")
        assert "PI-103" in result

    def test_rb1_preserved(self):
        result = numbers_to_words("Ginsenoside Rb1")
        assert "Rb1" in result

    def test_k2so_preserved(self):
        result = numbers_to_words("K-2SO voice")
        assert "K-2SO" in result

    def test_layer_labels_preserved(self):
        result = numbers_to_words("Layer 1: curated")
        assert "Layer 1" in result

    def test_year_in_context(self):
        result = numbers_to_words("In 2017, Sarnoski published")
        assert "twenty seventeen" in result

    def test_n_dollars(self):
        result = numbers_to_words("200 dollars per milligram")
        assert "two hundred dollars" in result

    def test_no_double_spaces(self):
        result = numbers_to_words("We screened 64,659 compounds.")
        assert "  " not in result
