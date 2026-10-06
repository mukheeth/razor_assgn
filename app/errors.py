"""Application-level errors that map WooCommerce HTTP failures to agent-facing messages.

These are the only error types the MCP layer should catch and surface.
Raw stack traces, HTTP headers, and credentials are never included.
"""


class WooCommerceConnectorError(Exception):
    """Base class for all connector errors."""


class AuthenticationError(WooCommerceConnectorError):
    """Credentials are missing, invalid, or lack permission."""


class NotFoundError(WooCommerceConnectorError):
    """Requested resource does not exist."""


class RateLimitError(WooCommerceConnectorError):
    """WooCommerce rate limit hit; caller should back off."""


class ValidationError(WooCommerceConnectorError):
    """Request parameters are invalid."""


class UpstreamServiceError(WooCommerceConnectorError):
    """WooCommerce is unavailable or returned an unexpected error."""
