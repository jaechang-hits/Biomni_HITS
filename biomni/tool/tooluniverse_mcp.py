from fastmcp import FastMCP
from tooluniverse.execute_function import ToolUniverse

mcp = FastMCP('ToolUniverse MCP', stateless_http=True)
engine = ToolUniverse()
engine.load_tools()

@mcp.tool()
def FDA_get_active_ingredient_info_by_drug_name(
    drug_name: str,
    limit: int,
    skip: int
) -> dict:
    return engine.run_one_function({
        "name": "FDA_get_active_ingredient_info_by_drug_name",
        "arguments": {
            "drug_name": drug_name,
            "limit": limit,
            "skip": skip
        }
    })

if __name__ == "__main__":
    mcp.run()