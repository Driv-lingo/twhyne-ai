# Copyright (c) 2025 Twhyne AI
# SPDX-License-Identifier: MIT
"""Verified snippet library: the SymPy trick, applied to code.

Math is instant because SymPy EVALUATES instead of generating. Most code
questions are the same classics, and for those the slow part - a 7B model
authoring ~700 tokens - is unnecessary. This library holds canonical
implementations with their tests; on a match the code is EXECUTED (with its
asserts) at answer time, which costs milliseconds, and ships with an honest
label. Novel requests still go to the model.

Matching is deliberately conservative: every required term must appear.
A miss costs nothing (falls through to generation); a wrong hit would give
a confidently irrelevant answer.
"""

import re

# Each entry: required term-groups (each group is alternatives - one must
# match), the code (with module-level asserts), and a display name.
LIBRARY = [
    {
        "name": "Reverse a linked list",
        "require": [("reverse",), ("linked list", "linkedlist")],
        "code": '''class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def reverse_linked_list(head):
    """Reverse a singly linked list; returns the new head."""
    prev = None
    current = head
    while current:
        nxt = current.next
        current.next = prev
        prev = current
        current = nxt
    return prev

def _to_list(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out

assert _to_list(reverse_linked_list(ListNode(1, ListNode(2, ListNode(3))))) == [3, 2, 1]
assert reverse_linked_list(None) is None
assert _to_list(reverse_linked_list(ListNode(7))) == [7]
''',
    },
    {
        "name": "Fibonacci numbers",
        "require": [("fibonacci", "fib ")],
        "code": '''def fibonacci(n):
    """n-th Fibonacci number (0-indexed: fib(0)=0, fib(1)=1). Iterative, O(n)."""
    if n < 0:
        raise ValueError("n must be >= 0")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

assert [fibonacci(i) for i in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]
assert fibonacci(0) == 0
assert fibonacci(20) == 6765
''',
    },
    {
        "name": "Binary search",
        "require": [("binary search", "binary-search")],
        "code": '''def binary_search(sorted_list, target):
    """Index of target in sorted_list, or -1. O(log n)."""
    lo, hi = 0, len(sorted_list) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_list[mid] == target:
            return mid
        if sorted_list[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

assert binary_search([1, 3, 5, 7, 9], 7) == 3
assert binary_search([], 1) == -1
assert binary_search([2, 4, 6], 5) == -1
''',
    },
    {
        "name": "Quicksort",
        "require": [("quicksort", "quick sort")],
        "code": '''def quicksort(items):
    """Sorted copy of items (not in-place). Average O(n log n)."""
    if len(items) <= 1:
        return list(items)
    pivot = items[len(items) // 2]
    left = [x for x in items if x < pivot]
    mid = [x for x in items if x == pivot]
    right = [x for x in items if x > pivot]
    return quicksort(left) + mid + quicksort(right)

assert quicksort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
assert quicksort([]) == []
assert quicksort([1]) == [1]
''',
    },
    {
        "name": "Palindrome check",
        "require": [("palindrome",)],
        "code": '''def is_palindrome(s):
    """True if s reads the same forwards and backwards (letters/digits only,
    case-insensitive)."""
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

assert is_palindrome("A man, a plan, a canal: Panama")
assert not is_palindrome("hello")
assert is_palindrome("")
''',
    },
    {
        "name": "Factorial",
        "require": [("factorial",)],
        "code": '''def factorial(n):
    """n! for n >= 0. Iterative (no recursion-depth limit)."""
    if n < 0:
        raise ValueError("n must be >= 0")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

assert factorial(0) == 1
assert factorial(5) == 120
assert factorial(10) == 3628800
''',
    },
    {
        "name": "FizzBuzz",
        "require": [("fizzbuzz", "fizz buzz")],
        "code": '''def fizzbuzz(n):
    """The classic: numbers 1..n, multiples of 3 -> Fizz, 5 -> Buzz, both -> FizzBuzz."""
    out = []
    for i in range(1, n + 1):
        s = ("Fizz" if i % 3 == 0 else "") + ("Buzz" if i % 5 == 0 else "")
        out.append(s or str(i))
    return out

assert fizzbuzz(5) == ["1", "2", "Fizz", "4", "Buzz"]
assert fizzbuzz(15)[14] == "FizzBuzz"
assert fizzbuzz(0) == []
''',
    },
    {
        "name": "Two sum",
        "require": [("two sum", "two-sum", "twosum")],
        "code": '''def two_sum(nums, target):
    """Indices of the two numbers adding to target, or None. O(n)."""
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return (seen[target - x], i)
        seen[x] = i
    return None

assert two_sum([2, 7, 11, 15], 9) == (0, 1)
assert two_sum([3, 2, 4], 6) == (1, 2)
assert two_sum([1, 2], 7) is None
''',
    },
    {
        "name": "Prime check",
        "require": [("prime",), ("check", "is", "test", "whether", "determine")],
        "code": '''def is_prime(n):
    """True if n is prime. Trial division up to sqrt(n)."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True

assert [x for x in range(20) if is_prime(x)] == [2, 3, 5, 7, 11, 13, 17, 19]
assert not is_prime(1)
assert is_prime(97)
''',
    },
    {
        "name": "Greatest common divisor",
        "require": [("gcd", "greatest common divisor")],
        "code": '''def gcd(a, b):
    """Greatest common divisor (Euclid's algorithm)."""
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a

assert gcd(48, 18) == 6
assert gcd(7, 13) == 1
assert gcd(0, 5) == 5
''',
    },
    {
        "name": "Reverse a string",
        "require": [("reverse",), ("string", "word", "text")],
        "code": '''def reverse_string(s):
    """The string reversed."""
    return s[::-1]

assert reverse_string("hello") == "olleh"
assert reverse_string("") == ""
assert reverse_string("ab") == "ba"
''',
    },
    {
        "name": "Remove duplicates from a list",
        "require": [("duplicate", "duplicates", "dedupe", "unique"),
                    ("list", "array")],
        "code": '''def remove_duplicates(items):
    """Copy of items with duplicates removed, first-seen order preserved."""
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

assert remove_duplicates([1, 2, 2, 3, 1]) == [1, 2, 3]
assert remove_duplicates([]) == []
assert remove_duplicates(["a", "a", "b"]) == ["a", "b"]
''',
    },
    {
        "name": "Binary tree depth-first traversal",
        "require": [("binary tree", "tree"), ("traverse", "traversal", "dfs",
                                              "depth-first", "depth first",
                                              "inorder", "in-order")],
        "code": '''class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def inorder(root):
    """In-order (left, node, right) traversal as a list. Iterative."""
    out, stack, node = [], [], root
    while stack or node:
        while node:
            stack.append(node)
            node = node.left
        node = stack.pop()
        out.append(node.val)
        node = node.right
    return out

_t = TreeNode(2, TreeNode(1), TreeNode(3))
assert inorder(_t) == [1, 2, 3]
assert inorder(None) == []
assert inorder(TreeNode(5)) == [5]
''',
    },
    {
        "name": "Merge sort",
        "require": [("merge sort", "mergesort")],
        "code": '''def merge_sort(items):
    """Sorted copy of items. Stable, O(n log n) worst case."""
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left, right = merge_sort(items[:mid]), merge_sort(items[mid:])
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    return out + left[i:] + right[j:]

assert merge_sort([5, 2, 8, 1, 9]) == [1, 2, 5, 8, 9]
assert merge_sort([]) == []
assert merge_sort([1, 1, 1]) == [1, 1, 1]
''',
    },
    {
        "name": "Bubble sort",
        "require": [("bubble sort", "bubblesort")],
        "code": '''def bubble_sort(items):
    """Sorted copy via bubble sort (educational; O(n^2))."""
    a = list(items)
    n = len(a)
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        if not swapped:
            break
    return a

assert bubble_sort([3, 1, 2]) == [1, 2, 3]
assert bubble_sort([]) == []
assert bubble_sort([2, 2, 1]) == [1, 2, 2]
''',
    },
    {
        "name": "Stack (LIFO)",
        "require": [("stack",), ("implement", "class", "create", "build", "write")],
        "code": '''class Stack:
    """LIFO stack with push, pop, peek, is_empty, len."""
    def __init__(self):
        self._items = []
    def push(self, item):
        self._items.append(item)
    def pop(self):
        if not self._items:
            raise IndexError("pop from empty stack")
        return self._items.pop()
    def peek(self):
        if not self._items:
            raise IndexError("peek at empty stack")
        return self._items[-1]
    def is_empty(self):
        return not self._items
    def __len__(self):
        return len(self._items)

_s = Stack()
_s.push(1); _s.push(2)
assert _s.peek() == 2 and len(_s) == 2
assert _s.pop() == 2 and _s.pop() == 1
assert _s.is_empty()
''',
    },
    {
        "name": "Queue (FIFO)",
        "require": [("queue",), ("implement", "class", "create", "build", "write")],
        "code": '''from collections import deque

class Queue:
    """FIFO queue with enqueue, dequeue, is_empty, len. O(1) both ends."""
    def __init__(self):
        self._items = deque()
    def enqueue(self, item):
        self._items.append(item)
    def dequeue(self):
        if not self._items:
            raise IndexError("dequeue from empty queue")
        return self._items.popleft()
    def is_empty(self):
        return not self._items
    def __len__(self):
        return len(self._items)

_q = Queue()
_q.enqueue('a'); _q.enqueue('b')
assert _q.dequeue() == 'a'
assert len(_q) == 1
assert not _q.is_empty()
''',
    },
    {
        "name": "Binary search tree",
        "require": [("binary search tree", "bst")],
        "code": '''class BSTNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def bst_insert(root, val):
    """Insert val; returns the (possibly new) root."""
    if root is None:
        return BSTNode(val)
    if val < root.val:
        root.left = bst_insert(root.left, val)
    else:
        root.right = bst_insert(root.right, val)
    return root

def bst_contains(root, val):
    while root:
        if val == root.val:
            return True
        root = root.left if val < root.val else root.right
    return False

_r = None
for _v in [5, 3, 8, 1]:
    _r = bst_insert(_r, _v)
assert bst_contains(_r, 3)
assert not bst_contains(_r, 7)
assert bst_contains(_r, 5)
''',
    },
    {
        "name": "Breadth-first search (graph)",
        "require": [("bfs", "breadth-first", "breadth first")],
        "code": '''from collections import deque

def bfs(graph, start):
    """Visit order from start over an adjacency-dict graph."""
    seen = {start}
    order = []
    q = deque([start])
    while q:
        node = q.popleft()
        order.append(node)
        for nxt in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return order

_g = {'a': ['b', 'c'], 'b': ['d'], 'c': ['d'], 'd': []}
assert bfs(_g, 'a') == ['a', 'b', 'c', 'd']
assert bfs(_g, 'd') == ['d']
assert bfs({}, 'x') == ['x']
''',
    },
    {
        "name": "Count word frequency",
        "require": [("word", "words"), ("count", "frequency", "frequencies", "occurrence")],
        "code": '''def word_frequency(text):
    """Case-insensitive word counts (letters/digits/apostrophes)."""
    import re
    counts = {}
    for w in re.findall(r"[A-Za-z0-9']+", text.lower()):
        counts[w] = counts.get(w, 0) + 1
    return counts

assert word_frequency("the cat and the hat") == {"the": 2, "cat": 1, "and": 1, "hat": 1}
assert word_frequency("") == {}
assert word_frequency("A a A") == {"a": 3}
''',
    },
    {
        "name": "Anagram check",
        "require": [("anagram",)],
        "code": '''def is_anagram(a, b):
    """True if a and b are anagrams (case-insensitive, ignores spaces)."""
    norm = lambda s: sorted(c for c in s.lower() if not c.isspace())
    return norm(a) == norm(b)

assert is_anagram("listen", "silent")
assert not is_anagram("hello", "world")
assert is_anagram("Dormitory", "dirty room")
''',
    },
    {
        "name": "Character frequency",
        "require": [("character", "letter", "char"), ("count", "frequency", "occurrence")],
        "code": '''def char_frequency(s):
    """Counts of each character in s."""
    counts = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    return counts

assert char_frequency("aab") == {"a": 2, "b": 1}
assert char_frequency("") == {}
assert char_frequency("zz z")[" "] == 1
''',
    },
    {
        "name": "Flatten a nested list",
        "require": [("flatten",), ("list", "lists", "array", "nested")],
        "code": '''def flatten(nested):
    """Flatten arbitrarily nested lists/tuples into one flat list."""
    out = []
    for item in nested:
        if isinstance(item, (list, tuple)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out

assert flatten([1, [2, [3, 4]], 5]) == [1, 2, 3, 4, 5]
assert flatten([]) == []
assert flatten([[], [1], ((2,),)]) == [1, 2]
''',
    },
    {
        "name": "Chunk a list",
        "require": [("chunk", "split", "batch"), ("list", "array"), ("size", "chunks", "groups", "pieces", "batches")],
        "code": '''def chunk_list(items, size):
    """Split items into consecutive chunks of at most `size`."""
    if size < 1:
        raise ValueError("size must be >= 1")
    return [items[i:i + size] for i in range(0, len(items), size)]

assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
assert chunk_list([], 3) == []
assert chunk_list([1], 5) == [[1]]
''',
    },
    {
        "name": "Merge two dictionaries",
        "require": [("merge", "combine"), ("dict", "dictionaries", "dictionary")],
        "code": '''def merge_dicts(a, b):
    """New dict with b's entries overriding a's on key conflicts."""
    out = dict(a)
    out.update(b)
    return out

assert merge_dicts({"x": 1}, {"y": 2}) == {"x": 1, "y": 2}
assert merge_dicts({"x": 1}, {"x": 9}) == {"x": 9}
assert merge_dicts({}, {}) == {}
''',
    },
    {
        "name": "Balanced parentheses",
        "require": [("balanced", "valid", "matching"), ("parenthes", "bracket", "brace")],
        "code": '''def is_balanced(s):
    """True if every ( [ { closes correctly."""
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for c in s:
        if c in '([{':
            stack.append(c)
        elif c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
    return not stack

assert is_balanced("({[]})")
assert not is_balanced("(]")
assert is_balanced("")
''',
    },
    {
        "name": "Longest common prefix",
        "require": [("longest common prefix",)],
        "code": '''def longest_common_prefix(strings):
    """Longest prefix shared by every string ('' if none)."""
    if not strings:
        return ""
    shortest = min(strings, key=len)
    for i, c in enumerate(shortest):
        if any(s[i] != c for s in strings):
            return shortest[:i]
    return shortest

assert longest_common_prefix(["flower", "flow", "flight"]) == "fl"
assert longest_common_prefix(["dog", "racecar"]) == ""
assert longest_common_prefix(["same", "same"]) == "same"
''',
    },
    {
        "name": "Second largest element",
        "require": [("second", "2nd"), ("largest", "biggest", "highest", "max")],
        "code": '''def second_largest(nums):
    """Second largest DISTINCT value, or None if it doesn't exist."""
    distinct = set(nums)
    if len(distinct) < 2:
        return None
    distinct.discard(max(distinct))
    return max(distinct)

assert second_largest([4, 1, 7, 7, 3]) == 4
assert second_largest([5]) is None
assert second_largest([2, 2, 2]) is None
''',
    },
    {
        "name": "Find the missing number",
        "require": [("missing",), ("number", "integer", "element")],
        "code": '''def missing_number(nums, n):
    """The one missing value from 0..n given the other n values. O(n)."""
    return n * (n + 1) // 2 - sum(nums)

assert missing_number([0, 1, 3], 3) == 2
assert missing_number([1, 2, 3], 3) == 0
assert missing_number([0], 1) == 1
''',
    },
    {
        "name": "Matrix transpose",
        "require": [("transpose",)],
        "code": '''def transpose(matrix):
    """Transpose a rectangular matrix (list of rows)."""
    return [list(col) for col in zip(*matrix)]

assert transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]
assert transpose([[1, 2, 3]]) == [[1], [2], [3]]
assert transpose([]) == []
''',
    },
    {
        "name": "Caesar cipher",
        "require": [("caesar",)],
        "code": '''def caesar(text, shift):
    """Caesar-shift letters (positive = right); other chars unchanged."""
    out = []
    for c in text:
        if c.isalpha():
            base = ord('A') if c.isupper() else ord('a')
            out.append(chr((ord(c) - base + shift) % 26 + base))
        else:
            out.append(c)
    return ''.join(out)

assert caesar("abc", 1) == "bcd"
assert caesar("XYZ", 3) == "ABC"
assert caesar(caesar("Hello, World!", 5), -5) == "Hello, World!"
''',
    },
    {
        "name": "Roman numerals",
        "require": [("roman",)],
        "code": '''def to_roman(n):
    """Integer (1-3999) to Roman numerals."""
    if not 1 <= n <= 3999:
        raise ValueError("1..3999 only")
    vals = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'),
            (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'),
            (5, 'V'), (4, 'IV'), (1, 'I')]
    out = []
    for v, sym in vals:
        while n >= v:
            out.append(sym)
            n -= v
    return ''.join(out)

assert to_roman(1994) == "MCMXCIV"
assert to_roman(4) == "IV"
assert to_roman(3999) == "MMMCMXCIX"
''',
    },
    {
        "name": "Temperature conversion",
        "require": [("celsius", "fahrenheit", "temperature")],
        "code": '''def c_to_f(celsius):
    """Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32

def f_to_c(fahrenheit):
    """Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9

assert c_to_f(0) == 32
assert c_to_f(100) == 212
assert abs(f_to_c(98.6) - 37) < 1e-9
''',
    },
    {
        "name": "Leap year check",
        "require": [("leap year", "leap-year")],
        "code": '''def is_leap_year(year):
    """Gregorian leap-year rule."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

assert is_leap_year(2024)
assert not is_leap_year(1900)
assert is_leap_year(2000)
''',
    },
    {
        "name": "Sort a dictionary by value",
        "require": [("sort",), ("dict", "dictionary"), ("value", "values")],
        "code": '''def sort_dict_by_value(d, reverse=False):
    """List of (key, value) pairs sorted by value."""
    return sorted(d.items(), key=lambda kv: kv[1], reverse=reverse)

assert sort_dict_by_value({"a": 3, "b": 1, "c": 2}) == [("b", 1), ("c", 2), ("a", 3)]
assert sort_dict_by_value({}, reverse=True) == []
assert sort_dict_by_value({"x": 5, "y": 5})[0][1] == 5
''',
    },
    {
        "name": "Merge overlapping intervals",
        "require": [("interval", "intervals"), ("merge", "overlap", "overlapping")],
        "code": '''def merge_intervals(intervals):
    """Merge overlapping [start, end] intervals; returns sorted merged list."""
    if not intervals:
        return []
    ivs = sorted(intervals)
    out = [list(ivs[0])]
    for start, end in ivs[1:]:
        if start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out

assert merge_intervals([[1, 3], [2, 6], [8, 10]]) == [[1, 6], [8, 10]]
assert merge_intervals([]) == []
assert merge_intervals([[1, 4], [4, 5]]) == [[1, 5]]
''',
    },
]


def match(prompt: str):
    """Return the library entry for prompt, or None. Conservative: every
    required group must have a hit; ties go to the most specific entry."""
    p = ' ' + re.sub(r'\s+', ' ', (prompt or '').lower()) + ' '
    best, best_req = None, 0
    for entry in LIBRARY:
        groups = entry["require"]
        if all(any(term in p for term in group) for group in groups):
            if len(groups) > best_req:
                best, best_req = entry, len(groups)
    return best
