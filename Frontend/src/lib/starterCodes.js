// Starter code shown in the editor for each problem and language.
// The function names / signatures must match Backend/code_runner.py.

export const STARTER_CODES = {
    1: {
        python: `def two_sum(nums, target):\n    # Write your code here\n    pass`,
        java: `class Solution {\n    public int[] twoSum(int[] nums, int target) {\n        // Write your code here\n        return new int[]{};\n    }\n}`,
        cpp: `#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        // Write your code here\n        return {};\n    }\n};`,
        c: `#include <stdio.h>\n\nvoid twoSum(int nums[], int n, int target) {\n    // Write your code here\n}`,
    },
    2: {
        python: `def binary_search(nums, target):\n    # Write your code here\n    return -1`,
        java: `class Solution {\n    public int search(int[] nums, int target) {\n        // Write your code here\n        return -1;\n    }\n}`,
        cpp: `#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    int search(vector<int>& nums, int target) {\n        // Write your code here\n        return -1;\n    }\n};`,
        c: `#include <stdio.h>\n\nint search(int nums[], int n, int target) {\n    // Write your code here\n    return -1;\n}`,
    },
    3: {
        python: `def is_valid(s):\n    # Write your code here\n    return False`,
        java: `class Solution {\n    public boolean isValid(String s) {\n        // Write your code here\n        return false;\n    }\n}`,
        cpp: `#include <string>\nusing namespace std;\n\nclass Solution {\npublic:\n    bool isValid(string s) {\n        // Write your code here\n        return false;\n    }\n};`,
        c: `#include <stdio.h>\n#include <stdbool.h>\n\nbool isValid(const char *s) {\n    // Write your code here\n    return false;\n}`,
    },
    4: {
        python: `def contains_duplicate(nums):\n    # Write your code here\n    return False`,
        java: `class Solution {\n    public boolean containsDuplicate(int[] nums) {\n        // Write your code here\n        return false;\n    }\n}`,
        cpp: `#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    bool containsDuplicate(vector<int>& nums) {\n        // Write your code here\n        return false;\n    }\n};`,
        c: `#include <stdio.h>\n#include <stdbool.h>\n\nbool containsDuplicate(int nums[], int n) {\n    // Write your code here\n    return false;\n}`,
    },
    5: {
        python: `def max_profit(prices):\n    # Write your code here\n    return 0`,
        java: `class Solution {\n    public int maxProfit(int[] prices) {\n        // Write your code here\n        return 0;\n    }\n}`,
        cpp: `#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    int maxProfit(vector<int>& prices) {\n        // Write your code here\n        return 0;\n    }\n};`,
        c: `#include <stdio.h>\n\nint maxProfit(int prices[], int n) {\n    // Write your code here\n    return 0;\n}`,
    },
    6: {
        python: `def is_anagram(s, t):\n    # Write your code here\n    return False`,
        java: `class Solution {\n    public boolean isAnagram(String s, String t) {\n        // Write your code here\n        return false;\n    }\n}`,
        cpp: `#include <string>\nusing namespace std;\n\nclass Solution {\npublic:\n    bool isAnagram(string s, string t) {\n        // Write your code here\n        return false;\n    }\n};`,
        c: `#include <stdio.h>\n#include <stdbool.h>\n\nbool isAnagram(const char *s, const char *t) {\n    // Write your code here\n    return false;\n}`,
    },
    7: {
        python: `def max_sub_array(nums):\n    # Write your code here\n    return 0`,
        java: `class Solution {\n    public int maxSubArray(int[] nums) {\n        // Write your code here\n        return 0;\n    }\n}`,
        cpp: `#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    int maxSubArray(vector<int>& nums) {\n        // Write your code here\n        return 0;\n    }\n};`,
        c: `#include <stdio.h>\n\nint maxSubArray(int nums[], int n) {\n    // Write your code here\n    return 0;\n}`,
    },
    8: {
        python: `def reverse_list(head):\n    # Write your code here\n    return head`,
        java: `class Solution {\n    public int[] reverseList(int[] head) {\n        // Write your code here\n        return head;\n    }\n}`,
        cpp: `#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> reverseList(vector<int>& head) {\n        // Write your code here\n        return head;\n    }\n};`,
        c: `#include <stdio.h>\n\nvoid reverseList(int nums[], int n) {\n    // Write your code here\n}`,
    },
};

const TITLE_CODES = {
    "two sum": STARTER_CODES[1],
    "binary search": STARTER_CODES[2],
    "valid parentheses": STARTER_CODES[3],
    "contains duplicate": STARTER_CODES[4],
    "best time to buy and sell stock": STARTER_CODES[5],
    "valid anagram": STARTER_CODES[6],
    "maximum subarray": STARTER_CODES[7],
    "reverse linked list": STARTER_CODES[8],
};

export const getStarterCode = (id, language, title = "") => {
    const normalizedTitle = String(title || "").trim().toLowerCase();

    if (TITLE_CODES[normalizedTitle]?.[language]) {
        return TITLE_CODES[normalizedTitle][language];
    }

    return STARTER_CODES[Number(id)]?.[language] || "";
};

export const LANGUAGES = [
    { value: "python", label: "Python 3", monaco: "python" },
    { value: "java", label: "Java", monaco: "java" },
    { value: "cpp", label: "C++", monaco: "cpp" },
    { value: "c", label: "C", monaco: "c" },
];

export const getLanguageLabel = (value) =>
    LANGUAGES.find((item) => item.value === value)?.label || value;
