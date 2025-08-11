"""
Embedding Service for efficient batch processing and caching.
Can run as standalone service or integrated component.
"""

import json
import hashlib
import logging
import threading
import numpy as np
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pickle
import gzip
from pathlib import Path

from .model_pool import model_pool_manager, initialize_model_pool
from ..cache.cache_manager import CacheManager

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingRequest:
    """Request for embedding generation."""
    texts: List[str]
    batch_size: int = 32
    normalize: bool = True
    request_id: Optional[str] = None


@dataclass 
class EmbeddingResponse:
    """Response containing embeddings."""
    embeddings: np.ndarray
    request_id: Optional[str] = None
    cache_hits: int = 0
    total_processed: int = 0


class EmbeddingService:
    """Service for managing embedding generation with caching and batching."""
    
    def __init__(self, 
                 model_name: str,
                 cache_enabled: bool = True,
                 cache_ttl: int = 3600,
                 batch_size: int = 32,
                 max_workers: int = 4):
        """
        Initialize embedding service.
        
        Args:
            model_name: Name of the sentence transformer model
            cache_enabled: Whether to enable caching
            cache_ttl: Cache time-to-live in seconds
            batch_size: Default batch size for processing
            max_workers: Maximum number of worker threads
        """
        self.model_name = model_name
        self.cache_enabled = cache_enabled
        self.cache_manager = CacheManager(ttl=cache_ttl) if cache_enabled else None
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_texts_processed': 0
        }
        
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return f"emb:{self.model_name}:{hashlib.md5(text.encode()).hexdigest()}"
    
    def _batch_encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """Encode texts in batches using model from pool."""
        with model_pool_manager.get_model(self.model_name) as model:
            embeddings = model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                normalize_embeddings=normalize
            )
            return embeddings
    
    def encode(self, 
               texts: Union[str, List[str]], 
               use_cache: bool = True,
               normalize: bool = True) -> np.ndarray:
        """
        Encode texts with caching support.
        
        Args:
            texts: Single text or list of texts to encode
            use_cache: Whether to use cache for this request
            normalize: Whether to normalize embeddings
            
        Returns:
            numpy array of embeddings
        """
        # Handle single text input
        if isinstance(texts, str):
            texts = [texts]
            single_input = True
        else:
            single_input = False
            
        self._stats['total_requests'] += 1
        self._stats['total_texts_processed'] += len(texts)
        
        # Check cache if enabled
        embeddings = []
        texts_to_encode = []
        text_indices = []
        
        if use_cache and self.cache_enabled:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                cached_emb = self.cache_manager.get(cache_key)
                
                if cached_emb is not None:
                    embeddings.append((i, cached_emb))
                    self._stats['cache_hits'] += 1
                else:
                    texts_to_encode.append(text)
                    text_indices.append(i)
                    self._stats['cache_misses'] += 1
        else:
            texts_to_encode = texts
            text_indices = list(range(len(texts)))
        
        # Encode texts not in cache
        if texts_to_encode:
            new_embeddings = self._batch_encode(texts_to_encode, normalize)
            
            # Cache new embeddings
            if use_cache and self.cache_enabled:
                for text, emb in zip(texts_to_encode, new_embeddings):
                    cache_key = self._get_cache_key(text)
                    self.cache_manager.set(cache_key, emb)
            
            # Combine with cached embeddings
            for idx, emb in zip(text_indices, new_embeddings):
                embeddings.append((idx, emb))
        
        # Sort by original index and extract embeddings
        embeddings.sort(key=lambda x: x[0])
        result = np.array([emb for _, emb in embeddings])
        
        # Return single embedding if input was single text
        if single_input:
            return result[0]
        return result
    
    async def encode_async(self,
                          texts: Union[str, List[str]],
                          use_cache: bool = True,
                          normalize: bool = True) -> np.ndarray:
        """Async version of encode method."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.encode,
            texts,
            use_cache,
            normalize
        )
    
    def batch_encode_with_metadata(self,
                                   data: Dict[str, List[str]],
                                   normalize: bool = True) -> Dict[str, np.ndarray]:
        """
        Encode multiple groups of texts with metadata.
        
        Args:
            data: Dictionary mapping keys to lists of texts
            normalize: Whether to normalize embeddings
            
        Returns:
            Dictionary mapping keys to embeddings
        """
        results = {}
        for key, texts in data.items():
            results[key] = self.encode(texts, normalize=normalize)
        return results
    
    def preload_cache(self, texts: List[str]):
        """Preload cache with frequently used texts."""
        logger.info(f"Preloading cache with {len(texts)} texts")
        self.encode(texts, use_cache=True)
        logger.info("Cache preload complete")
    
    def save_embeddings(self, embeddings: Dict[str, np.ndarray], filepath: Path):
        """Save embeddings to disk."""
        with gzip.open(filepath, 'wb') as f:
            pickle.dump(embeddings, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"Saved embeddings to {filepath}")
    
    def load_embeddings(self, filepath: Path) -> Dict[str, np.ndarray]:
        """Load embeddings from disk."""
        with gzip.open(filepath, 'rb') as f:
            embeddings = pickle.load(f)
        logger.info(f"Loaded embeddings from {filepath}")
        return embeddings
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        stats = self._stats.copy()
        if self.cache_enabled:
            stats['cache_stats'] = self.cache_manager.get_stats()
        stats['model_pool_stats'] = model_pool_manager.get_all_stats()
        return stats
    
    def clear_cache(self):
        """Clear the embedding cache."""
        if self.cache_enabled:
            self.cache_manager.clear()
            logger.info("Embedding cache cleared")
    
    def shutdown(self):
        """Shutdown the service and cleanup resources."""
        self.executor.shutdown(wait=True)
        if self.cache_enabled:
            self.cache_manager.shutdown()
        logger.info("Embedding service shutdown complete")


class EmbeddingServicePool:
    """Manage multiple embedding services for different models."""
    
    def __init__(self):
        self.services: Dict[str, EmbeddingService] = {}
        self._lock = threading.Lock()
    
    def get_service(self, 
                   model_name: str,
                   cache_enabled: bool = True,
                   **kwargs) -> EmbeddingService:
        """Get or create an embedding service for the model."""
        if model_name not in self.services:
            with self._lock:
                if model_name not in self.services:
                    service = EmbeddingService(
                        model_name=model_name,
                        cache_enabled=cache_enabled,
                        **kwargs
                    )
                    self.services[model_name] = service
                    logger.info(f"Created embedding service for {model_name}")
        
        return self.services[model_name]
    
    def shutdown_all(self):
        """Shutdown all services."""
        for name, service in self.services.items():
            logger.info(f"Shutting down service: {name}")
            service.shutdown()
        self.services.clear()


# Global service pool
embedding_service_pool = EmbeddingServicePool()


def get_embedding_service(model_name: str, **kwargs) -> EmbeddingService:
    """Get embedding service for the specified model."""
    return embedding_service_pool.get_service(model_name, **kwargs)