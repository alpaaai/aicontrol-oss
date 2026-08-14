"""Real MCP server (FastMCP, streamable-http) -- the clean contrast target
in the admission_scanning demo scenario."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("claims-status-mcp", host="127.0.0.1", port=8902)


@mcp.tool()
def get_claim_status(claim_id: str) -> str:
    """Get the current status of an insurance claim."""
    return f"claim {claim_id}: approved, payout scheduled"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
