"""Known-correct solutions for every problem in every language, using the starter signatures."""

TEST_CASES = {
    1: [("nums=[2,7,11,15], target=9", "[0,1]"), ("nums=[3,2,4], target=6", "[1,2]"), ("nums=[3,3], target=6", "[0,1]")],
    2: [("nums=[-1,0,3,5,9,12], target=9", "4"), ("nums=[-1,0,3,5,9,12], target=2", "-1"), ("nums=[5], target=5", "0")],
    3: [('s="()"', "true"), ('s="()[]{}"', "true"), ('s="(]"', "false"), ('s=""', "true")],
    4: [("nums=[1,2,3,1]", "true"), ("nums=[1,2,3,4]", "false"), ("nums=[]", "false")],
    5: [("prices=[7,1,5,3,6,4]", "5"), ("prices=[7,6,4,3,1]", "0")],
    6: [('s="anagram", t="nagaram"', "true"), ('s="rat", t="car"', "false"), ('s="a b,c", t="c,b a"', "true")],
    7: [("nums=[-2,1,-3,4,-1,2,1,-5,4]", "6"), ("nums=[1]", "1"), ("nums=[5,4,-1,7,8]", "23")],
    8: [("head=[1,2,3,4,5]", "[5,4,3,2,1]"), ("head=[1,2]", "[2,1]"), ("head=[]", "[]")],
}

PYTHON = {
    1: """
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
    return []
""",
    2: """
def binary_search(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""",
    3: """
def is_valid(s):
    stack, pairs = [], {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in '([{':
            stack.append(ch)
        elif not stack or stack.pop() != pairs[ch]:
            return False
    return not stack
""",
    4: "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n",
    5: """
def max_profit(prices):
    best, low = 0, float('inf')
    for p in prices:
        low = min(low, p)
        best = max(best, p - low)
    return best
""",
    6: "def is_anagram(s, t):\n    return sorted(s) == sorted(t)\n",
    7: """
def max_sub_array(nums):
    best = cur = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best
""",
    8: "def reverse_list(head):\n    return head[::-1]\n",
}

JAVA = {
    1: """
import java.util.*;
class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            Integer j = seen.get(target - nums[i]);
            if (j != null) return new int[]{j, i};
            seen.put(nums[i], i);
        }
        return new int[]{};
    }
}
""",
    2: """
class Solution {
    public int search(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return mid;
            if (nums[mid] < target) lo = mid + 1; else hi = mid - 1;
        }
        return -1;
    }
}
""",
    3: """
import java.util.*;
class Solution {
    public boolean isValid(String s) {
        Deque<Character> st = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if (c == '(' || c == '[' || c == '{') st.push(c);
            else {
                if (st.isEmpty()) return false;
                char o = st.pop();
                if ((c == ')' && o != '(') || (c == ']' && o != '[') || (c == '}' && o != '{')) return false;
            }
        }
        return st.isEmpty();
    }
}
""",
    4: """
import java.util.*;
class Solution {
    public boolean containsDuplicate(int[] nums) {
        Set<Integer> s = new HashSet<>();
        for (int n : nums) if (!s.add(n)) return true;
        return false;
    }
}
""",
    5: """
class Solution {
    public int maxProfit(int[] prices) {
        int best = 0, low = Integer.MAX_VALUE;
        for (int p : prices) { low = Math.min(low, p); best = Math.max(best, p - low); }
        return best;
    }
}
""",
    6: """
import java.util.*;
class Solution {
    public boolean isAnagram(String s, String t) {
        char[] a = s.toCharArray(), b = t.toCharArray();
        Arrays.sort(a); Arrays.sort(b);
        return Arrays.equals(a, b);
    }
}
""",
    7: """
class Solution {
    public int maxSubArray(int[] nums) {
        int best = nums[0], cur = nums[0];
        for (int i = 1; i < nums.length; i++) { cur = Math.max(nums[i], cur + nums[i]); best = Math.max(best, cur); }
        return best;
    }
}
""",
    8: """
class Solution {
    public int[] reverseList(int[] head) {
        int[] r = new int[head.length];
        for (int i = 0; i < head.length; i++) r[i] = head[head.length - 1 - i];
        return r;
    }
}
""",
}

CPP = {
    1: """
#include <vector>
#include <unordered_map>
using namespace std;
class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> seen;
        for (int i = 0; i < (int) nums.size(); i++) {
            auto it = seen.find(target - nums[i]);
            if (it != seen.end()) return {it->second, i};
            seen[nums[i]] = i;
        }
        return {};
    }
};
""",
    2: """
class Solution {
public:
    int search(vector<int>& nums, int target) {
        int lo = 0, hi = (int) nums.size() - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return mid;
            if (nums[mid] < target) lo = mid + 1; else hi = mid - 1;
        }
        return -1;
    }
};
""",
    3: """
#include <string>
#include <stack>
using namespace std;
class Solution {
public:
    bool isValid(string s) {
        stack<char> st;
        for (char c : s) {
            if (c == '(' || c == '[' || c == '{') st.push(c);
            else {
                if (st.empty()) return false;
                char o = st.top(); st.pop();
                if ((c == ')' && o != '(') || (c == ']' && o != '[') || (c == '}' && o != '{')) return false;
            }
        }
        return st.empty();
    }
};
""",
    4: """
class Solution {
public:
    bool containsDuplicate(vector<int>& nums) {
        unordered_set<int> s;
        for (int n : nums) if (!s.insert(n).second) return true;
        return false;
    }
};
""",
    5: """
class Solution {
public:
    int maxProfit(vector<int>& prices) {
        int best = 0, low = INT_MAX;
        for (int p : prices) { low = min(low, p); best = max(best, p - low); }
        return best;
    }
};
""",
    6: """
class Solution {
public:
    bool isAnagram(string s, string t) {
        sort(s.begin(), s.end()); sort(t.begin(), t.end());
        return s == t;
    }
};
""",
    7: """
class Solution {
public:
    int maxSubArray(vector<int>& nums) {
        int best = nums[0], cur = nums[0];
        for (size_t i = 1; i < nums.size(); i++) { cur = max(nums[i], cur + nums[i]); best = max(best, cur); }
        return best;
    }
};
""",
    8: """
class Solution {
public:
    vector<int> reverseList(vector<int>& head) {
        return vector<int>(head.rbegin(), head.rend());
    }
};
""",
}

C = {
    1: """
#include <stdio.h>
void twoSum(int nums[], int n, int target) {
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (nums[i] + nums[j] == target) { printf("[%d,%d]", i, j); return; }
    printf("[]");
}
""",
    2: """
int search(int nums[], int n, int target) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) return mid;
        if (nums[mid] < target) lo = mid + 1; else hi = mid - 1;
    }
    return -1;
}
""",
    3: """
#include <stdbool.h>
#include <string.h>
bool isValid(const char *s) {
    size_t n = strlen(s);
    char *st = malloc(n + 1);
    int top = 0;
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        if (c == '(' || c == '[' || c == '{') st[top++] = c;
        else {
            if (top == 0) { free(st); return false; }
            char o = st[--top];
            if ((c == ')' && o != '(') || (c == ']' && o != '[') || (c == '}' && o != '{')) { free(st); return false; }
        }
    }
    free(st);
    return top == 0;
}
""",
    4: """
bool containsDuplicate(int nums[], int n) {
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (nums[i] == nums[j]) return true;
    return false;
}
""",
    5: """
int maxProfit(int prices[], int n) {
    int best = 0, low = INT_MAX;
    for (int i = 0; i < n; i++) {
        if (prices[i] < low) low = prices[i];
        if (prices[i] - low > best) best = prices[i] - low;
    }
    return best;
}
""",
    6: """
bool isAnagram(const char *s, const char *t) {
    int count[256] = {0};
    if (strlen(s) != strlen(t)) return false;
    for (; *s; s++, t++) { count[(unsigned char) *s]++; count[(unsigned char) *t]--; }
    for (int i = 0; i < 256; i++) if (count[i]) return false;
    return true;
}
""",
    7: """
int maxSubArray(int nums[], int n) {
    int best = nums[0], cur = nums[0];
    for (int i = 1; i < n; i++) {
        cur = nums[i] > cur + nums[i] ? nums[i] : cur + nums[i];
        if (cur > best) best = cur;
    }
    return best;
}
""",
    8: """
void reverseList(int nums[], int n) {
    for (int i = 0, j = n - 1; i < j; i++, j--) { int t = nums[i]; nums[i] = nums[j]; nums[j] = t; }
}
""",
}

SOLUTIONS = {"python": PYTHON, "java": JAVA, "cpp": CPP, "c": C}
