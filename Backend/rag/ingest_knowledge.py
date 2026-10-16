"""
Load the Coding Mentor knowledge base into Supabase (pgvector).

Run from the Backend folder:
    python -m rag.ingest_knowledge            # add documents that are missing
    python -m rag.ingest_knowledge --force    # re-embed and replace all documents

Safe to run repeatedly: documents are matched by title, so re-running does not
create duplicates.
"""

import argparse
import logging
import os
import sys

# Allow `python rag/ingest_knowledge.py` as well as `python -m rag.ingest_knowledge`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402,F401
from database import supabase  # noqa: E402
from rag.embeddings import get_embeddings  # noqa: E402

logger = logging.getLogger("ingest")


documents = [
    {
        "title": "Binary Search Pattern",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Binary search is used when the search space is sorted or can be divided
into smaller monotonic sections.

Basic idea:
1. Find the middle element.
2. Compare the middle element with the target.
3. If equal, return the result.
4. If target is smaller, search the left half.
5. If target is larger, search the right half.

Time complexity:
O(log n)

Space complexity:
O(1) for the iterative approach.

Common mistakes:
- Incorrect mid calculation.
- Incorrect left/right boundary update.
- Infinite loops caused by not changing the search boundaries.
- Using binary search when the search space is not suitable.
"""
    },

    {
        "title": "Two Sum Pattern",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Two Sum asks us to find two numbers whose sum equals a target.

A brute force approach checks every pair.

Brute force:
Time complexity: O(n^2)
Space complexity: O(1)

An optimized approach uses a hash map.

For each number:
1. Calculate complement = target - current number.
2. Check whether the complement already exists in the hash map.
3. If it exists, return the stored index and current index.
4. Otherwise store the current number and its index.

Optimized complexity:
Time: O(n)
Space: O(n)

The hashing pattern is useful when a problem asks for fast membership
checking, complements, duplicates, or frequency counting.
"""
    },

    {
        "title": "Valid Parentheses Pattern",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Valid Parentheses is a classic stack problem.

Use a stack to store opening brackets.

For every character:
- If it is an opening bracket, push it.
- If it is a closing bracket, check the top of the stack.
- The closing bracket must match the most recent opening bracket.
- Remove the opening bracket after a successful match.

At the end, the stack must be empty.

Time complexity:
O(n)

Space complexity:
O(n)

This problem demonstrates the Last-In-First-Out property of stacks.
Stacks are commonly useful for:
- Balanced brackets
- Next greater element
- Expression evaluation
- Undo operations
- Parsing
"""
    },

    {
        "title": "Hashing Pattern",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Hashing is useful when we need fast lookup or membership checking.

Common applications:
- Frequency counting
- Detecting duplicates
- Finding complements
- Checking whether an element has appeared before
- Mapping values to indexes

Average lookup complexity in a hash table is approximately O(1).

Typical pattern:

Create a dictionary or hash map.

For each element:
1. Check whether the required value exists.
2. If it exists, use the stored information.
3. Otherwise store the current information.

Hashing often converts an O(n^2) brute force solution into O(n).
"""
    },

    {
        "title": "Time Complexity Basics",
        "category": "Interview",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Time complexity describes how the running time of an algorithm grows
as the input size increases.

Common complexities:

O(1)
Constant time.

O(log n)
Logarithmic time, commonly seen in binary search.

O(n)
Linear time, commonly seen when scanning an array once.

O(n log n)
Commonly seen in efficient comparison-based sorting algorithms.

O(n^2)
Quadratic time, commonly produced by nested loops over the same input.

When comparing solutions, consider both time and space complexity.
"""
    },
    {
        "title": "Sliding Minimum Pattern (Best Time to Buy and Sell Stock)",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Best Time to Buy and Sell Stock asks for the maximum profit from one buy
followed by one later sell.

Brute force checks every (buy, sell) pair:
Time complexity: O(n^2)
Space complexity: O(1)

Optimized one-pass idea:
1. Keep the lowest price seen so far (the best day to have bought).
2. For each price, the best profit if we sell today is price - lowest.
3. Track the maximum of those profits.
4. If prices only go down, the answer is 0 (do not trade).

Time complexity: O(n)
Space complexity: O(1)

Common mistakes:
- Selling before buying (using a minimum that comes after the current day).
- Initializing the answer to a negative number instead of 0.
- Returning the lowest price or the highest price instead of the difference.
"""
    },

    {
        "title": "Kadane's Algorithm (Maximum Subarray)",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Maximum Subarray asks for the largest sum of a contiguous subarray.

Brute force tries every subarray:
Time complexity: O(n^2) with running sums, O(n^3) without.

Kadane's algorithm (dynamic programming in O(1) space):
1. current = best sum of a subarray that ENDS at the current index.
2. For each number x: current = max(x, current + x)
   (either start a new subarray at x or extend the previous one).
3. best = max(best, current).
4. Initialize both with the first element, not 0, so all-negative arrays work.

Time complexity: O(n)
Space complexity: O(1)

Common mistakes:
- Initializing best to 0, which gives the wrong answer for [-3, -1, -2].
- Resetting current to 0 instead of comparing with x.
- Confusing subarray (contiguous) with subsequence.
"""
    },

    {
        "title": "Reversing a Linked List",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Reversing a singly linked list is done with three pointers:
prev = null, current = head.

While current is not null:
1. Save next = current.next.
2. Point current.next to prev (reverse the link).
3. Move prev = current and current = next.

At the end prev is the new head.

Time complexity: O(n)
Space complexity: O(1) iterative, O(n) recursive (call stack).

When the list is represented as an array, the same idea is the two-pointer
swap: swap left and right, move left forward and right backward until they
meet.

Common mistakes:
- Losing the rest of the list by not saving next before changing links.
- Returning the old head instead of prev.
- Off-by-one errors in the two-pointer loop condition (use left < right).
"""
    },

    {
        "title": "Frequency Counting (Anagrams and Duplicates)",
        "category": "DSA",
        "source": "Coding Mentor Knowledge Base",
        "content": """
Frequency counting stores how many times each value appears.

Valid Anagram:
- If lengths differ, the strings cannot be anagrams.
- Count characters of s, subtract counts for t; every count must end at 0.
- With a fixed alphabet (26 letters) the count array uses O(1) space.
- Sorting both strings and comparing also works in O(n log n).

Contains Duplicate:
- Insert numbers into a hash set; if a number is already present, a
  duplicate exists.
- Time O(n), space O(n).
- Sorting first and comparing neighbours uses O(n log n) time and O(1)
  extra space.

Common mistakes:
- Forgetting to compare lengths first.
- Using nested loops (O(n^2)) when a hash set or count array is enough.
- Not handling empty inputs.
"""
    },

    {
        "title": "Debugging Checklist for Coding Problems",
        "category": "Interview",
        "source": "Coding Mentor Knowledge Base",
        "content": """
When a solution fails a test case:

1. Re-read the problem: return type, 0- vs 1-based indexes, edge cases.
2. Dry run the failing input by hand and write down every variable.
3. Check boundaries: empty input, one element, all equal, negatives, maximum values.
4. Check loop bounds (< vs <=) and index updates (mid + 1 / mid - 1).
5. Make sure every code path returns a value.
6. Print intermediate values (debug output) and compare with your dry run.

Wrong Answer usually means a logic or edge-case bug.
Runtime Error usually means index out of range, null access or division by zero.
Time Limit Exceeded usually means an infinite loop or an algorithm that is too slow
(for example O(n^2) when O(n) is expected).
"""
    }
]


def existing_titles() -> set:
    response = supabase.table("knowledge_documents").select("title").execute()
    return {row["title"] for row in (response.data or [])}


def main(force: bool = False) -> None:
    embeddings = get_embeddings()
    already_loaded = set() if force else existing_titles()
    pending = [doc for doc in documents if doc["title"] not in already_loaded]

    if not pending:
        print("Knowledge base is already up to date. Use --force to re-embed everything.")
        return

    print(f"Embedding {len(pending)} document(s)...")
    # embed_documents uses the RETRIEVAL_DOCUMENT task type, which pairs with the
    # RETRIEVAL_QUERY embeddings used at question time for better matches.
    vectors = embeddings.embed_documents([doc["content"] for doc in pending])

    for document, vector in zip(pending, vectors):
        row = {
            "title": document["title"],
            "content": document["content"].strip(),
            "category": document["category"],
            "source": document["source"],
            "metadata": {"type": "coding_knowledge"},
            "embedding": vector,
        }
        if force:
            supabase.table("knowledge_documents").delete().eq("title", document["title"]).execute()
        supabase.table("knowledge_documents").insert(row).execute()
        print(f"  Inserted: {document['title']}")

    print("\nRAG INGESTION COMPLETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="re-embed and replace every document")
    main(force=parser.parse_args().force)
