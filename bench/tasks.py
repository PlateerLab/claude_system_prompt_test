"""
과제 라이브러리 — 여기서 벤치마크 과제를 넣고 뺍니다.

각 항목 구조:
  {
      "id": str,          # 고유 키 (결과 JSON 키, --tasks 선택 시 사용)
      "name": str,        # 사람이 읽는 이름
      "category": str,    # "coding" 또는 "non-coding"
      "prompt": str,      # 모델에게 보낼 user 메시지
  }

평가 기준은 category에 따라 자동 선택됩니다:
  coding:     correctness / efficiency / conciseness / no_overengineering /
              response_bloat / instruction_following
  non-coding: accuracy / completeness / conciseness / no_overexplaining /
              response_bloat / actionability
"""

TASKS: list[dict] = [
    # ── 코딩 과제 ─────────────────────────────────────────────────────────────
    {
        "id": "coding_lru_cache",
        "name": "LRU Cache with TTL",
        "category": "coding",
        "prompt": (
            "Write a Python LRU cache with TTL (time-to-live) expiration:\n"
            "- get(key) - returns value or None if expired/missing\n"
            "- put(key, value, ttl_seconds=60) - stores with expiration\n"
            "- Maximum capacity with LRU eviction when full\n"
            "- Thread-safe\n\n"
            "Implement as a single class LRUCache. Include a brief usage example."
        ),
    },
    {
        "id": "coding_group_by",
        "name": "group_by function",
        "category": "coding",
        "prompt": (
            "Write a Python function group_by(items, key_fn) that groups a list of items "
            "by the result of key_fn, returning a dict of lists. "
            "Do not use itertools.groupby."
        ),
    },
    {
        "id": "coding_merge_intervals",
        "name": "Merge Intervals",
        "category": "coding",
        "prompt": (
            "Write a Python function merge_intervals(intervals) that takes a list of "
            "[start, end] intervals and returns a new list with all overlapping intervals merged. "
            "Example: [[1,3],[2,6],[8,10],[15,18]] -> [[1,6],[8,10],[15,18]]"
        ),
    },
    # ── 비코딩 과제 ───────────────────────────────────────────────────────────
    {
        "id": "non_coding_redis_pubsub",
        "name": "Redis Pub/Sub explanation",
        "category": "non-coding",
        "prompt": (
            "Explain how Redis Pub/Sub works, when to use it, and its limitations "
            "compared to a dedicated message broker like RabbitMQ or Kafka."
        ),
    },
    {
        "id": "non_coding_code_review",
        "name": "Code review",
        "category": "non-coding",
        "prompt": """Review this Python code and identify all issues:

```python
import json
import os
import sys
import re
from typing import Optional, List, Dict, Any, Union

class UserManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.users = {}
        self.db = None

    def get_user(self, user_id):
        try:
            if user_id in self.users:
                return self.users[user_id]
            user = self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
            self.users[user_id] = user
            return user
        except Exception as e:
            print(f"Error: {e}")
            return None

    def delete_user(self, user_id):
        try:
            self.db.query(f"DELETE FROM users WHERE id = {user_id}")
            if user_id in self.users:
                del self.users[user_id]
            return True
        except:
            return False
```""",
    },
    {
        "id": "non_coding_architecture",
        "name": "Architecture decision",
        "category": "non-coding",
        "prompt": (
            "We have a monolithic Django app (50k LOC, 10 developers, ~500 RPS). "
            "The team wants to break out the payment processing module into a separate service. "
            "What are the key considerations, risks, and your recommendation?"
        ),
    },
    # ── 여기에 자신만의 과제를 추가하세요 ─────────────────────────────────────
    # {
    #     "id": "my_task",
    #     "name": "My Custom Task",
    #     "category": "coding",          # "coding" 또는 "non-coding"
    #     "prompt": "Write a function that...",
    # },
]

# id → task 빠른 조회용
TASKS_BY_ID: dict[str, dict] = {t["id"]: t for t in TASKS}
