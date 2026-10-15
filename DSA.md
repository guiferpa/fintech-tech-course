[Português](DSA.pt-BR.md)

# DSA track

Many fintechs, and almost every company hiring internationally, run a coding round (data structures and algorithms) before system design. This track prepares you for it without taking time from the capstone days: **the first 30 minutes of every Monday to Wednesday session** (for example 19:00 to 19:30, with the session ending at 22:30). Thursday and Friday stay 100% capstone.

Over 13 weeks you solve the classic interview problems, grouped by pattern, from warm-ups (Two Sum, Top K) to the hard ones (LFU Cache, Median from Data Stream, Word Break). Checkpoint weeks and the final week use the slot for re-solving and recorded mock coding interviews.

## Rules

- **Without AI**, like the capstone days. No ChatGPT, Claude, Copilot or AI autocomplete.
- **30-minute timebox.** If you are stuck after 20 minutes, read only the approach in the LeetCode editorial (not the code), close it, code it yourself and mark the problem **redo**.
- **Use the language you will interview in.** TypeScript keeps it consistent with the course; Python is also common in interviews.
- **Keep your solutions** in a `dsa/` folder of your practice repository, one file per problem with the complexity in a comment.

## Method for each problem (out loud, as in an interview)

1. Restate the problem and ask about edge cases (empty input, duplicates, negatives, size limits).
2. Work through one small example by hand.
3. Say the brute force and its complexity.
4. Find the pattern (the table below names it) and the better complexity.
5. Code it, then test it by hand with the example and one edge case.
6. State the final time and space complexity.

## Flashcards

For every problem, create one card with the **trick** (not the code): "Subarray sum equals K: which structure, and why does it work with negatives?". Tag it `dsa`. In checkpoints, review the `dsa` tag. See the [flashcards guide](FLASHCARDS.md).

## Schedule

| Week | Day | Problem | Pattern |
| --- | --- | --- | --- |
| 1 (M1) | Mon | [Two Sum](https://leetcode.com/problems/two-sum/)<br>[Two Sum II](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) | hash map<br>two pointers on a sorted array |
| 1 (M1) | Tue | [3Sum](https://leetcode.com/problems/3sum/) | sort + two pointers, generalizes to k-sum |
| 1 (M1) | Wed | [Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) | heap, then bucket sort in O(n) |
| 2 (M2) | Mon | [Kth Largest Element in a Stream](https://leetcode.com/problems/kth-largest-element-in-a-stream/) | min-heap of size k |
| 2 (M2) | Tue | [Maximum Subarray](https://leetcode.com/problems/maximum-subarray/)<br>[Maximum Product Subarray](https://leetcode.com/problems/maximum-product-subarray/) | Kadane<br>Kadane variation (track min and max) |
| 2 (M2) | Wed | [Longest Substring Without Repeating Characters](https://leetcode.com/problems/longest-substring-without-repeating-characters/) | sliding window |
| 3 (M3) | Mon | [Subarray Sum Equals K](https://leetcode.com/problems/subarray-sum-equals-k/) | prefix sum + hash map |
| 3 (M3) | Tue | [Merge Intervals](https://leetcode.com/problems/merge-intervals/) | intervals: sort by start |
| 3 (M3) | Wed | [Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) | binary search on the answer |
| 4 (M4) | Mon | [Capacity To Ship Packages Within D Days](https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/) | binary search on the answer (capacity, days, weights) |
| 4 (M4) | Tue | [Clone Graph](https://leetcode.com/problems/clone-graph/) | graph DFS/BFS + hash map of copies |
| 4 (M4) | Wed | [Copy List with Random Pointer](https://leetcode.com/problems/copy-list-with-random-pointer/) | hash map, then O(1) space interleaving |
| 5 (C1) | Mon | Re-solve 2 problems you marked "redo" in weeks 1 to 4, from scratch, no hints. | — |
| 5 (C1) | Tue | Mock coding interview (30 min, recorded): pick a random problem from weeks 1 to 4 and solve it explaining out loud, as in an interview. | — |
| 5 (C1) | Wed | Complexity review: write the time and space complexity of every problem so far from memory, check, and turn mistakes into flashcards. | — |
| 6 (M5) | Mon | [Course Schedule](https://leetcode.com/problems/course-schedule/)<br><sub>Same idea as deadlock detection in a wait-for graph.</sub> | cycle detection in a directed graph (3-color DFS) |
| 6 (M5) | Tue | [Course Schedule II](https://leetcode.com/problems/course-schedule-ii/) | topological sort (Kahn) |
| 6 (M5) | Wed | [Accounts Merge](https://leetcode.com/problems/accounts-merge/) | union-find |
| 7 (M6) | Mon | [Word Ladder](https://leetcode.com/problems/word-ladder/) | BFS shortest path |
| 7 (M6) | Tue | [Word Ladder (optimization)](https://leetcode.com/problems/word-ladder/)<br><sub>Redo yesterday's solution, now with bidirectional BFS, and compare the runtimes.</sub> | bidirectional BFS + wildcard map |
| 7 (M6) | Wed | [Merge K Sorted Lists](https://leetcode.com/problems/merge-k-sorted-lists/)<br><sub>Same shape as merging sorted event streams in reconciliation.</sub> | min-heap, or divide and conquer |
| 8 (M7) | Mon | Rate limiter: token bucket<br><sub>No LeetCode link: write a class with allow(userId, now) and unit tests for bursts and refill.</sub> | design + code: allow(userId, now) |
| 8 (M7) | Tue | Rate limiter: sliding window<br><sub>Same interface as yesterday; compare memory use and accuracy at window boundaries.</sub> | sliding window log, then sliding window counter |
| 8 (M7) | Wed | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) | two pointers, then monotonic stack |
| 9 (C2) | Mon | Re-solve 2 problems you marked "redo" in weeks 6 to 8, from scratch, no hints. | — |
| 9 (C2) | Tue | Mock coding interview (30 min, recorded): pick a random problem from weeks 6 to 8 and solve it explaining out loud, as in an interview. | — |
| 9 (C2) | Wed | Complexity review: write the time and space complexity of every problem so far from memory, check, and turn mistakes into flashcards. | — |
| 10 (M8) | Mon | [LRU Cache](https://leetcode.com/problems/lru-cache/) | hash map + doubly linked list |
| 10 (M8) | Tue | [LFU Cache (1/2)](https://leetcode.com/problems/lfu-cache/)<br><sub>Design the structures and get get/put working.</sub> | hash map + frequency buckets |
| 10 (M8) | Wed | [LFU Cache (2/2)](https://leetcode.com/problems/lfu-cache/)<br><sub>Finish, then test eviction ties (same frequency, least recently used goes first).</sub> | hash map + frequency buckets |
| 11 (M9) | Mon | [Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) | two heaps |
| 11 (M9) | Tue | [Task Scheduler](https://leetcode.com/problems/task-scheduler/) | greedy + max-heap |
| 11 (M9) | Wed | Priority scheduler<br><sub>No LeetCode link: schedule(task, priority, runAt) and next(now), plus retry with exponential backoff for failed tasks.</sub> | design + code: heap ordered by (runAt, priority) |
| 12 (M10) | Mon | [Longest Increasing Subsequence](https://leetcode.com/problems/longest-increasing-subsequence/) | O(n²) DP, then patience sorting in O(n log n) |
| 12 (M10) | Tue | [Serialize and Deserialize Binary Tree](https://leetcode.com/problems/serialize-and-deserialize-binary-tree/) | preorder DFS with null markers |
| 12 (M10) | Wed | [Word Break](https://leetcode.com/problems/word-break/) | DP, then trie to speed up prefix checks |
| 13 (F) | Mon | Mock coding interview 1 (30 min, recorded): a random medium problem from the whole list. | — |
| 13 (F) | Tue | Mock coding interview 2 (30 min, recorded): a random hard problem from the whole list. | — |
| 13 (F) | Wed | Final review: re-solve whatever is still marked "redo" and update your patterns cheat sheet. | — |

Two problems were added to the classic lists because they come up often in fintech interviews: the **rate limiter** (week 8) and the **priority scheduler with retries** (week 11). They have no LeetCode link: write a small class with unit tests.
