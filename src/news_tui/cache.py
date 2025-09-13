from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger("news")

class Cache:
    def __init__(self, cache_dir: str, ttl: int):
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, key: str) -> str:
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed_key}.json")

    def get(self, key: str) -> Optional[Any]:
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)

            if time.time() - data.get("timestamp", 0) > self.ttl:
                logger.debug("Cache expired for key: %s", key)
                return None

            logger.debug("Cache hit for key: %s", key)
            return data.get("value")
        except (IOError, json.JSONDecodeError) as e:
            logger.warning("Failed to read from cache file %s: %s", cache_path, e)
            return None

    def set(self, key: str, value: Any) -> None:
        cache_path = self._get_cache_path(key)
        data = {
            "timestamp": time.time(),
            "value": value,
        }
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
            logger.debug("Cache set for key: %s", key)
        except IOError as e:
            logger.warning("Failed to write to cache file %s: %s", cache_path, e)

    def clear(self) -> None:
        """Clear all items from the cache."""
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error("Failed to delete cache file %s: %s", file_path, e)
        logger.info("Cache cleared.")
