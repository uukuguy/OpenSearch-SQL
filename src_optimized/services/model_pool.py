"""
Model Pool Manager for efficient model resource management.
Implements singleton pattern with thread-safe model pool.
"""

import os
import queue
import threading
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for model pool."""
    model_name: str
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    pool_size: int = 3
    max_wait_time: float = 30.0
    cache_folder: str = 'model/'


class ModelPool:
    """Thread-safe model pool implementation."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.pool = queue.Queue(maxsize=config.pool_size)
        self._lock = threading.Lock()
        self._initialized = False
        self._total_created = 0
        
    def initialize(self):
        """Initialize the model pool with pre-loaded models."""
        with self._lock:
            if self._initialized:
                return
                
            logger.info(f"Initializing model pool with {self.config.pool_size} instances")
            for i in range(self.config.pool_size):
                model = self._create_model()
                self.pool.put(model)
                logger.info(f"Model {i+1}/{self.config.pool_size} loaded")
                
            self._initialized = True
            logger.info("Model pool initialization complete")
    
    def _create_model(self) -> SentenceTransformer:
        """Create a new model instance."""
        self._total_created += 1
        return SentenceTransformer(
            self.config.model_name,
            device=self.config.device,
            cache_folder=self.config.cache_folder
        )
    
    @contextmanager
    def get_model(self):
        """Context manager to safely get and return a model from the pool."""
        model = None
        try:
            model = self.pool.get(timeout=self.config.max_wait_time)
            yield model
        except queue.Empty:
            raise TimeoutError(f"Could not get model from pool within {self.config.max_wait_time} seconds")
        finally:
            if model is not None:
                self.pool.put(model)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            'pool_size': self.config.pool_size,
            'available': self.pool.qsize(),
            'in_use': self.config.pool_size - self.pool.qsize(),
            'total_created': self._total_created,
            'device': self.config.device
        }


class ModelPoolManager:
    """Singleton manager for model pools."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._pools = {}
                    cls._instance._default_config = None
        return cls._instance
    
    def set_default_config(self, config: ModelConfig):
        """Set default configuration for new pools."""
        self._default_config = config
    
    def get_pool(self, model_name: Optional[str] = None) -> ModelPool:
        """Get or create a model pool for the specified model."""
        if model_name is None:
            if self._default_config is None:
                raise ValueError("No default configuration set")
            model_name = self._default_config.model_name
            
        if model_name not in self._pools:
            with self._lock:
                if model_name not in self._pools:
                    config = self._default_config if self._default_config else ModelConfig(model_name)
                    if config.model_name != model_name:
                        config = ModelConfig(model_name)
                    pool = ModelPool(config)
                    pool.initialize()
                    self._pools[model_name] = pool
                    
        return self._pools[model_name]
    
    def get_model(self, model_name: Optional[str] = None):
        """Get a model context manager from the pool."""
        pool = self.get_pool(model_name)
        return pool.get_model()
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all pools."""
        return {name: pool.get_stats() for name, pool in self._pools.items()}
    
    def shutdown(self):
        """Shutdown all model pools and cleanup resources."""
        logger.info("Shutting down model pools")
        with self._lock:
            for name, pool in self._pools.items():
                logger.info(f"Shutting down pool: {name}")
                # Clear the queue
                while not pool.pool.empty():
                    try:
                        pool.pool.get_nowait()
                    except queue.Empty:
                        break
            self._pools.clear()
        logger.info("Model pools shutdown complete")


# Global singleton instance
model_pool_manager = ModelPoolManager()


def initialize_model_pool(model_name: str, device: str = 'auto', pool_size: int = 3):
    """Initialize the global model pool with configuration."""
    if device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    config = ModelConfig(
        model_name=model_name,
        device=device,
        pool_size=pool_size
    )
    
    model_pool_manager.set_default_config(config)
    logger.info(f"Model pool initialized: {model_name} on {device} with pool size {pool_size}")
    
    return model_pool_manager


def get_model():
    """Get a model from the default pool."""
    return model_pool_manager.get_model()