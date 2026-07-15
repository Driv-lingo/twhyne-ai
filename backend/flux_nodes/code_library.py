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
