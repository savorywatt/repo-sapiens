"""Utility modules for the automation system.

This package provides shared utilities and helpers used across the automation
platform, including logging, caching, retries, and API integrations.

Key Components:
    - logging_config: Structured logging setup with structlog
    - caching: Async caching with TTL support
    - retry: Retry utilities for transient failures
    - batch_operations: Batch processing for API efficiency
    - connection_pool: HTTP connection pooling
    - cost_optimizer: Model selection based on task complexity
    - status_reporter: Issue/PR status updates
    - interactive: Interactive Q&A via issue comments
    - mcp_client: MCP (Model Context Protocol) client
    - helpers: Common utility functions

Features:
    - Structured JSON logging
    - Async cache with automatic expiration
    - Intelligent retry with exponential backoff
    - Batch API operations
    - HTTP/2 multiplexing
    - Cost-aware model selection
    - Status tracking and reporting

Example:
    >>> from automation.utils import configure_logging, get_logger
    >>> configure_logging("DEBUG")
    >>> log = get_logger(__name__)
    >>> log.info("operation_started")
"""
