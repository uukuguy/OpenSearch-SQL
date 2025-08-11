"""
Cache Manager for multi-level caching support.
Supports in-memory LRU cache and optional Redis backend.
"""

import time
import pickle
from ..utils.loguru_config import get_logger
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from dataclasses import dataclass

logger = get_logger(__name__)

# Try to import Redis, but make it optional
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. Only in-memory caching will be used.")


@dataclass
class CacheConfig:
    """Configuration for cache manager."""
    max_size: int = 10000
    ttl: int = 3600  # Time to live in seconds
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    use_redis: bool = False


class LRUCache:
    """Thread-safe LRU cache implementation."""
    
    def __init__(self, max_size: int = 10000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self.cache:
                self._stats['misses'] += 1
                return None
            
            # Check if expired
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                self._stats['expired'] += 1
                self._stats['misses'] += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self._stats['hits'] += 1
            return self.cache[key]
    
    def set(self, key: str, value: Any):
        """Set value in cache."""
        with self._lock:
            # Remove oldest if at capacity
            if key not in self.cache and len(self.cache) >= self.max_size:
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                del self.timestamps[oldest]
                self._stats['evictions'] += 1
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
            self.cache.move_to_end(key)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self._stats['evictions'],
                'expired': self._stats['expired']
            }


class RedisCache:
    """Redis cache wrapper."""
    
    def __init__(self, config: CacheConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not installed. Install with: pip install redis")
        
        self.ttl = config.ttl
        self.client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            password=config.redis_password,
            decode_responses=False  # We'll handle encoding/decoding
        )
        self._stats = {
            'hits': 0,
            'misses': 0
        }
        
        # Test connection
        try:
            self.client.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        try:
            value = self.client.get(key)
            if value is None:
                self._stats['misses'] += 1
                return None
            
            self._stats['hits'] += 1
            return pickle.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any):
        """Set value in Redis with TTL."""
        try:
            serialized = pickle.dumps(value)
            self.client.setex(key, self.ttl, serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def clear(self):
        """Clear all keys in the current database."""
        try:
            self.client.flushdb()
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        try:
            info = self.client.info('memory')
            redis_stats = {
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': self.client.info('clients').get('connected_clients', 0)
            }
        except:
            redis_stats = {}
        
        return {
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': hit_rate,
            **redis_stats
        }


class CacheManager:
    """Multi-level cache manager with L1 (in-memory) and optional L2 (Redis) cache."""
    
    def __init__(self, 
                 max_size: int = 10000,
                 ttl: int = 3600,
                 use_redis: bool = False,
                 redis_config: Optional[CacheConfig] = None):
        """
        Initialize cache manager.
        
        Args:
            max_size: Maximum size for in-memory cache
            ttl: Time to live in seconds
            use_redis: Whether to use Redis as L2 cache
            redis_config: Redis configuration
        """
        # L1 cache (always enabled)
        self.l1_cache = LRUCache(max_size=max_size, ttl=ttl)
        
        # L2 cache (optional)
        self.l2_cache = None
        if use_redis and REDIS_AVAILABLE:
            try:
                config = redis_config or CacheConfig(ttl=ttl, use_redis=True)
                self.l2_cache = RedisCache(config)
                logger.info("L2 cache (Redis) enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}")
                logger.info("Falling back to L1 cache only")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (checks L1 first, then L2)."""
        # Check L1
        value = self.l1_cache.get(key)
        if value is not None:
            return value
        
        # Check L2 if available
        if self.l2_cache:
            value = self.l2_cache.get(key)
            if value is not None:
                # Promote to L1
                self.l1_cache.set(key, value)
                return value
        
        return None
    
    def set(self, key: str, value: Any):
        """Set value in both L1 and L2 cache."""
        self.l1_cache.set(key, value)
        
        if self.l2_cache:
            self.l2_cache.set(key, value)
    
    def delete(self, key: str) -> bool:
        """Delete key from all cache levels."""
        l1_deleted = self.l1_cache.delete(key)
        l2_deleted = False
        
        if self.l2_cache:
            l2_deleted = self.l2_cache.delete(key)
        
        return l1_deleted or l2_deleted
    
    def clear(self):
        """Clear all cache levels."""
        self.l1_cache.clear()
        
        if self.l2_cache:
            self.l2_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all cache levels."""
        stats = {
            'l1_cache': self.l1_cache.get_stats()
        }
        
        if self.l2_cache:
            stats['l2_cache'] = self.l2_cache.get_stats()
        
        return stats
    
    def shutdown(self):
        """Cleanup cache resources."""
        logger.info("Shutting down cache manager")
        # L1 cache doesn't need explicit shutdown
        # Redis connection will be closed automatically