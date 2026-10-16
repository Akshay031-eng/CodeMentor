-- =============================================================================
-- AI Coding Mentor - sample data (8 problems + test cases)
--
-- For a NEW Supabase project: run supabase_schema.sql first, then this file
-- (Dashboard -> SQL Editor). Safe to re-run: existing problems are kept, and
-- test cases are only added to problems that have none yet.
--
-- Problem ids 1-8 must match PROBLEMS in Backend/code_runner.py.
-- Test input format: name=value pairs, e.g.  nums=[2,7], target=9  or  s="()"
-- =============================================================================

insert into public.problems (id, title, difficulty, topic, description, constraints)
values
    (1, 'Two Sum', 'Easy', 'Hashing',
     'Given an array of integers nums and an integer target, return the indices of the two numbers that add up to target.

Each input has exactly one solution, and you may not use the same element twice. Return the two indices as a list, for example [0,1]. The order of the two indices does not matter.',
     '2 <= nums.length <= 10^4
-10^9 <= nums[i] <= 10^9
Exactly one valid answer exists'),
    (2, 'Binary Search', 'Easy', 'Binary Search',
     'Given a sorted array of distinct integers nums and an integer target, return the index of target in nums. If target is not present, return -1.

Your solution should run in O(log n) time.',
     '1 <= nums.length <= 10^4
All values in nums are distinct
nums is sorted in ascending order'),
    (3, 'Valid Parentheses', 'Easy', 'Stack',
     'Given a string s containing only the characters ''('', '')'', ''{'', ''}'', ''['' and '']'', decide whether it is valid.

A string is valid when every opening bracket is closed by the same type of bracket, and brackets are closed in the correct order. Return true or false.',
     '0 <= s.length <= 10^4
s contains only ()[]{}'),
    (4, 'Contains Duplicate', 'Easy', 'Hashing',
     'Given an integer array nums, return true if any value appears at least twice, and false if every element is distinct.',
     '0 <= nums.length <= 10^5
-10^9 <= nums[i] <= 10^9'),
    (5, 'Best Time to Buy and Sell Stock', 'Easy', 'Arrays',
     'You are given an array prices where prices[i] is the price of a stock on day i.

Choose one day to buy and a later day to sell to maximise your profit. Return the maximum profit, or 0 if no profit is possible.',
     '1 <= prices.length <= 10^5
0 <= prices[i] <= 10^4'),
    (6, 'Valid Anagram', 'Easy', 'Strings',
     'Given two strings s and t, return true if t is an anagram of s - that is, t uses exactly the same characters as s the same number of times - and false otherwise.',
     '1 <= s.length, t.length <= 5 * 10^4'),
    (7, 'Maximum Subarray', 'Medium', 'Dynamic Programming',
     'Given an integer array nums, find the contiguous subarray (containing at least one number) with the largest sum, and return that sum.',
     '1 <= nums.length <= 10^5
-10^4 <= nums[i] <= 10^4'),
    (8, 'Reverse Linked List', 'Easy', 'Linked List',
     'You are given the values of a singly linked list in order (as an array). Reverse the list and return the values in their new order.

Try to do it in place with O(1) extra space - the same two-pointer idea used to reverse a real linked list.',
     '0 <= number of nodes <= 5000
-5000 <= Node.val <= 5000')
on conflict (id) do nothing;

-- Keep the id sequence ahead of the explicit ids above.
select setval(pg_get_serial_sequence('public.problems', 'id'), greatest((select max(id) from public.problems), 1));

insert into public.test_cases (problem_id, input, expected_output)
select v.problem_id, v.input, v.expected_output
from (values
    (1, 'nums=[2,7,11,15], target=9', '[0,1]'),
    (1, 'nums=[3,2,4], target=6', '[1,2]'),
    (1, 'nums=[3,3], target=6', '[0,1]'),
    (1, 'nums=[-3,4,3,90], target=0', '[0,2]'),
    (1, 'nums=[1,5,9,13,2], target=15', '[3,4]'),
    (2, 'nums=[-1,0,3,5,9,12], target=9', '4'),
    (2, 'nums=[-1,0,3,5,9,12], target=2', '-1'),
    (2, 'nums=[5], target=5', '0'),
    (2, 'nums=[1,3,5,7,9,11], target=1', '0'),
    (2, 'nums=[1,3,5,7,9,11], target=11', '5'),
    (3, 's="()"', 'true'),
    (3, 's="()[]{}"', 'true'),
    (3, 's="(]"', 'false'),
    (3, 's="([)]"', 'false'),
    (3, 's="{[]}"', 'true'),
    (3, 's="(("', 'false'),
    (4, 'nums=[1,2,3,1]', 'true'),
    (4, 'nums=[1,2,3,4]', 'false'),
    (4, 'nums=[1,1,1,3,3,4,3,2,4,2]', 'true'),
    (4, 'nums=[7]', 'false'),
    (5, 'prices=[7,1,5,3,6,4]', '5'),
    (5, 'prices=[7,6,4,3,1]', '0'),
    (5, 'prices=[2,4,1]', '2'),
    (5, 'prices=[3,2,6,5,0,3]', '4'),
    (6, 's="anagram", t="nagaram"', 'true'),
    (6, 's="rat", t="car"', 'false'),
    (6, 's="listen", t="silent"', 'true'),
    (6, 's="a", t="ab"', 'false'),
    (7, 'nums=[-2,1,-3,4,-1,2,1,-5,4]', '6'),
    (7, 'nums=[1]', '1'),
    (7, 'nums=[5,4,-1,7,8]', '23'),
    (7, 'nums=[-3,-1,-2]', '-1'),
    (8, 'head=[1,2,3,4,5]', '[5,4,3,2,1]'),
    (8, 'head=[1,2]', '[2,1]'),
    (8, 'head=[]', '[]'),
    (8, 'head=[7]', '[7]')
) as v(problem_id, input, expected_output)
where not exists (
    select 1 from public.test_cases t where t.problem_id = v.problem_id
);
