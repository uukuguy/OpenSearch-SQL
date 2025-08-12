"""
Optimized services for model and embedding management
"""

from .model_pool import (
    ModelPool,
    ModelPoolManager,
    ModelConfig,
    initialize_model_pool,
    get_model,
    model_pool_manager
)

from .embedding_service import (
    EmbeddingService,
    EmbeddingServicePool,
    EmbeddingRequest,
    EmbeddingResponse,
    get_embedding_service,
    embedding_service_pool
)

__all__ = [
    'ModelPool',
    'ModelPoolManager',
    'ModelConfig',
    'initialize_model_pool',
    'get_model',
    'model_pool_manager',
    'EmbeddingService',
    'EmbeddingServicePool',
    'EmbeddingRequest',
    'EmbeddingResponse',
    'get_embedding_service',
    'embedding_service_pool'
]