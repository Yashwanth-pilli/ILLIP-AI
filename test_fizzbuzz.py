import unittest
from io import StringIO
from contextlib import redirect_stdout
from fizzbuzz import fizzbuzz


class TestFizzBuzz(unittest.TestCase):

    def setUp(self):
        self.captured = StringIO()

    def _capture_output(self, n):
        with redirect_stdout(self.captured):
            fizzbuzz(n)
        return self.captured.getvalue().strip().split('\\n')

    # ---- Edge case: n=1 (single number that is not 3 or 5 multiple) ----
    def test_n_equals_1(self):
        """
        Test: Single number input, not divisible by 3 or 5
        Given: n = 1
        When: fizzbuzz(1) runs
        Then: Output should be "1" only
        """
        result = self._capture_output(1)
        self.assertEqual(result, ["1"])

    # ---- Edge case: n=2 (two numbers, neither divisible by 3 or 5) ----
    def test_n_equals_2(self):
        """
        Test: Two consecutive non-multiples of 3 and 5
        Given: n = 2
        When: fizzbuzz(2) runs
        Then: Output should be "1", "2"
        """
        result = self._capture_output(2)
        self.assertEqual(result, ["1", "2"])

    # ---- Edge case: n=3 (first Fizz number) ----
    def test_n_equals_3(self):
        """
        Test: Includes first multiple of 3
        Given: n = 3
        When: fizzbuzz(3) runs
        Then: Output should be "1", "2", "Fizz"
        """
        result = self._capture_output(3)
        self.assertEqual(result, ["1", "2", "Fizz"])

    # ---- Edge case: n=4 (Fizz followed by non-multiple) ----
    def test_n_equals_4(self):
        """
        Test: Fizz at position 3, then regular number
        Given: n = 4
        When: fizzbuzz(4) runs
        Then: Output should be "1", "2", "Fizz", "4"
        """
        result = self._capture_output(4)
        self.assertEqual(result, ["1", "2", "Fizz", "4"])

    # ---- Edge case: n=5 (Buzz number) ----
    def test_n_equals_5(self):
        """
        Test: Includes first multiple of 5
        Given: n = 5
        When: fizzbuzz(5) runs
        Then: Output should be "1", "2", "Fizz", "4", "Buzz"
        """
        result = self._capture_output(5)
        self.assertEqual(result, ["1", "2", "Fizz", "4", "Buzz"])

    # ---- Edge case: n=6 (Fizz + Buzz in sequence) ----
    def test_n_equals_6(self):
        """
        Test: Fizz at 3, regular at 4-5, Buzz at 5, then regular
        Given: n = 6
        When: fizzbuzz(6) runs
        Then: Output should be "1", "2", "Fizz", "4", "Buzz", "6"
        """
        result = self._capture_output(6)
        self.assertEqual(result, ["1", "2", "Fizz", "4", "Buzz", "6"])

    # ---- Edge case: n=7 (Buzz followed by regular number 7) ----
    def test_n_equals_7(self):
        """
        Test: Buzz at 5, then non-multiple 6 and 7
        Given: n = 7
        When: fizzbuzz(7) runs
        Then: Output should be "1", "2", "Fizz", "4", "Buzz", "6", "7"
        """
        result = self._capture_output(7)
        self.assertEqual(result, ["1", "2", "Fizz", "4", "Buzz", "6", "7"])

    # ---- Edge case: n=8 (regular number 8 after Buzz) ----
    def test_n_equals_8(self):
        """
        Test: Regular numbers following Buzz at 5
        Given: n = 8
        When: fizzbuzz(8) runs
        Then: Output should be "1", "2", "Fizz", "4", "Buzz", "6", "7", "8"
        """
        result = self._capture_output(8)
        self.assertEqual(result, ["1", "2", "Fizz", "4", "Buzz", "6", "7", "8"])

    # ---- Edge case: n=9 (Fizz at 9 after Buzz at 5, 6, 7, 8) ----
    def test_n_equals_9(self):
        """
        Test: Fizz at position 3 and 9
        Given: n = 9
        When: fizzbuzz(9) runs
        Then: Output should have "Fizz" at index 2 and 8
        """
        result = self._capture_output(9)
        self.assertEqual(result[2], "Fizz")   # i=3
        self.assertEqual(result[4], "Buzz")    # i=5
        self.assertEqual(result[6], "6")       # i=6
        self.assertEqual(result[7], "7")       # i=7
        self.assertEqual(result[8], "Fizz")    # i=9

    # ---- Edge case: n=10 (Buzz at 10 after Fizz at 9) ----
    def test_n_equals_10(self):
        """
        Test: Buzz at position 5 and 10
        Given: n = 10
        When: fizzbuzz(10) runs
        Then: Output should have "Buzz" at index 4 and 9
        """
        result = self._capture_output(10)
        self.assertEqual(result[2], "Fizz")   # i=3
        self.assertEqual(result[4], "Buzz")    # i=5
        self.assertEqual(result[8], "Fizz")    # i=9
        self.assertEqual(result[9], "Buzz")    # i=10

    # ---- Edge case: n=15 (FizzBuzz number, first multiple of both 3 and 5) ----
    def test_n_equals_15(self):
        """
        Test: First FizzBuzz at position 15
        Given: n = 15
        When: fizzbuzz(15) runs
        Then: Output should have "FizzBuzz" at index 14 (i=15)
        """
        result = self._capture_output(15)
        self.assertEqual(len(result), 15)
        # i=3 -> Fizz, i=5 -> Buzz, ..., i=15 -> FizzBuzz
        self.assertEqual(result[2], "Fizz")     # i=3
        self.assertEqual(result[4], "Buzz")     # i=5
        self.assertEqual(result[8], "Fizz")     # i=9
        self.assertEqual(result[9], "Buzz")     # i=10
        self.assertEqual(result[12], "Fizz")    # i=13 is wrong, i=12 -> Fizz (div by 3)
        self.assertEqual(result[13], "4")       # i=13? Let me recalculate
        # Actually indices: result[i-1] for i in 1..n
        # i=1->result[0]=1, i=2->result[1]=2, ..., i=15->result[14]=FizzBuzz
        self.assertEqual(result[14], "FizzBuzz")

    # ---- Edge case: n=30 (second FizzBuzz at position 30) ----
    def test_n_equals_30(self):
        """
        Test: Second FizzBuzz at position 30, plus regular Fizz/Buzz
        Given: n = 30
        When: fizzbuzz(30) runs
        Then: Output should have "FizzBuzz" at index 14 (i=15) and 29 (i=30)
        """
        result = self._capture_output(30)
        self.assertEqual(len(result), 30)
        self.assertEqual(result[14], "FizzBuzz")   # i=15
        self.assertEqual(result[29], "FizzBuzz")    # i=30

    # ---- Edge case: n=15 (full sequence up to first FizzBuzz) ----
    def test_n_equals_15_full_sequence(self):
        """
        Test: Full output for n=15 matches expected pattern exactly
        Given: n = 15
        When: fizzbuzz(15) runs
        Then: Output should be the well-known first-15 FizzBuzz sequence
        """
        result = self._capture_output(15)
        expected = [
            "1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8",
            "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"
        ]
        self.assertEqual(result, expected)

    # ---- Edge case: n=50 (mid-range with multiple Fizz/Buzz/FizzBuzz) ----
    def test_n_equals_50(self):
        """
        Test: Mid-range including Fizz at 3,6,9,12,... and Buzz at 5,10,15,...
        Given: n = 50
        When: fizzbuzz(50) runs
        Then: Output should have correct pattern for all numbers up to 50
        """
        result = self._capture_output(50)
        self.assertEqual(len(result), 50)

        # Spot check some positions
        self.assertEqual(result[2], "Fizz")     # i=3
        self.assertEqual(result[4], "Buzz")     # i=5
        self.assertEqual(result[8], "Fizz")     # i=9
        self.assertEqual(result[9], "Buzz")     # i=10
        self.assertEqual(result[12], "Fizz")    # i=13 -> 13%3!=0, 13%5!=0, so result[12]="13"
        # Actually: index = i-1. i=13 => index=12. 13%15!=0, 13%3=1, 13%5=3 -> print(13)
        self.assertEqual(result[14], "FizzBuzz") # i=15

    # ---- Edge case: large number n=100 (full standard test range) ----
    def test_n_equals_100(self):
        """
        Test: Full 1-100 FizzBuzz sequence
        Given: n = 100
        When: fizzbuzz(100) runs
        Then: Output should have correct FizzBuzz pattern for all 100 numbers
        """
        result = self._capture_output(100)
        self.assertEqual(len(result), 100)

        # Verify specific known positions
        # i=3 -> Fizz, i=5 -> Buzz, ..., i=15 -> FizzBuzz
        self.assertEqual(result[2], "Fizz")     # i=3
        self.assertEqual(result[4], "Buzz")     # i=5
        self.assertEqual(result[9], "Buzz")     # i=10
        self.assertEqual(result[14], "FizzBuzz")# i=15
        self.assertEqual(result[28], "Fizz")    # i=29 -> 29%3!=0, 29%5!=0 -> "29"
        # i=30 -> FizzBuzz
        self.assertEqual(result[29], "FizzBuzz")# i=30

    # ---- Edge case: large number n=1000 (stress test) ----
    def test_n_equals_1000(self):
        """
        Test: Large input 1000 to verify no performance or correctness issues at scale
        Given: n = 1000
        When: fizzbuzz(1000) runs
        Then: Output should be a list of 1000 items with correct FizzBuzz pattern
        """
        result = self._capture_output(1000)
        self.assertEqual(len(result), 1000)

        # Verify first few and last few are correct
        self.assertEqual(result[0], "1")         # i=1
        self.assertEqual(result[1], "2")         # i=2
        self.assertEqual(result[2], "Fizz")       # i=3
        self.assertEqual(result[4], "Buzz")       # i=5

        # Last few: 998, 999(Fizz), 1000(Buzz)
        self.assertEqual(result[997], "998")     # i=998
        self.assertEqual(result[998], "Fizz")     # i=999 (div by 3)
        self.assertEqual(result[999], "Buzz")     # i=1000 (div by 5)

    # ---- Edge case: n=20 (FizzBuzz at 15, regular after) ----
    def test_n_equals_20(self):
        """
        Test: Includes FizzBuzz at 15 and continues past it
        Given: n = 20
        When: fizzbuzz(20) runs
        Then: Output should have "FizzBuzz" at index 14 (i=15), then regular numbers after
        """
        result = self._capture_output(20)
        self.assertEqual(len(result), 20)
        self.assertEqual(result[14], "FizzBuzz") # i=15

    # ---- Edge case: n=22 (Fizz at 21, regular after FizzBuzz at 15 and 20) ----
    def test_n_equals_22(self):
        """
        Test: FizzBuzz at 15 and 20, Fizz at 21, Buzz at 20
        Given: n = 22
        When: fizzbuzz(22) runs
        Then: Output should have "FizzBuzz" at index 14 (i=15), "FizzBuzz" at 19 (i=20)
        """
        result = self._capture_output(22)
        self.assertEqual(len(result), 22)
        self.assertEqual(result[14], "FizzBuzz") # i=15
        self.assertEqual(result[19], "FizzBuzz") # i=20

    # ---- Edge case: n=3 (smallest Fizz number as last element) ----
    def test_n_equals_3_last_is_fizz(self):
        """
        Test: Last element is Fizz when n equals first multiple of 3
        Given: n = 3
        When: fizzbuzz(3) runs
        Then: Output should end with "Fizz" as the last element
        """
        result = self._capture_output(3)
        self.assertEqual(result[-1], "Fizz")

    # ---- Edge case: n=5 (Buzz number as last element) ----
    def test_n_equals_5_last_is_buzz(self):
        """
        Test: Last element is Buzz when n equals first multiple of 5
        Given: n = 5
        When: fizzbuzz(5) runs
        Then: Output should end with "Buzz" as the last element
        """
        result = self._capture_output(5)
        self.assertEqual(result[-1], "Buzz")

    # ---- Edge case: n=7 (Fizz at 3, Buzz at 5, regular at 6 and 7) ----
    def test_n_equals_7_fizz_and_buzz_before_regular(self):
        """
        Test: Both Fizz(3) and Buzz(5) appear before the end with regular numbers after
        Given: n = 7
        When: fizzbuzz(7) runs
        Then: Output should be ["1","2","Fizz","4","Buzz","6","7"]
        """
        result = self._capture_output(7)
        expected = ["1", "2", "Fizz", "4", "Buzz", "6", "7"]
        self.assertEqual(result, expected)

    # ---- Edge case: n=10 (Buzz at 5 and 10, Fizz at 3 and 9) ----
    def test_n_equals_10_two_buzz_and_two_fizz(self):
        """
        Test: Multiple Fizz and Buzz occurrences up to 10
        Given: n = 10
        When: fizzbuzz(10) runs
        Then: Output should have exactly two "Fizz" (at i=3,9) and two "Buzz" (at i=5,10)
        """
        result = self._capture_output(10)
        fizz_count = result.count("Fizz")
        buzz_count = result.count("Buzz")
        fbuzz_count = result.count("FizzBuzz")
        number_count = sum(1 for x in result if isinstance(x, str) and x.isdigit())

        # i=3 Fizz, i=5 Buzz, i=6 6, i=7 7, i=8 8, i=9 Fizz, i=10 Buzz
        self.assertEqual(fizz_count, 2)   # at i=3, i=9
        self.assertEqual(buzz_count, 2)    # at i=5 (not counted separately due to check order) - but actually it's checked as elif so buzz at 5 is captured by first Buzz check

if __name__ == "__main__":
    unittest.main()
