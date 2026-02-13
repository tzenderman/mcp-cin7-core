"""MCP server for Cin7 Core — tool, resource, and prompt registration."""

from __future__ import annotations

from fastmcp import FastMCP

from .resources import (
    auth as auth_tools,
    products,
    suppliers,
    sales,
    purchase_orders,
    stock,
    snapshots,
    templates,
    prompts,
)
from .utils.logging import setup_logging

setup_logging()


def create_mcp_server(auth=None):
    """Create and configure the FastMCP server with all tools, resources, and prompts.

    Args:
        auth: Optional auth provider (e.g., ScalekitProvider) for OAuth
    """
    mcp = FastMCP("mcp-cin7-core", auth=auth)

    # -- Tools: auth --------------------------------------------------------
    mcp.tool()(auth_tools.cin7_status)
    mcp.tool()(auth_tools.cin7_me)

    # -- Tools: products ----------------------------------------------------
    mcp.tool()(products.cin7_products)
    mcp.tool()(products.cin7_get_product)
    mcp.tool()(products.cin7_create_product)
    mcp.tool()(products.cin7_update_product)

    # -- Tools: suppliers ---------------------------------------------------
    mcp.tool()(suppliers.cin7_suppliers)
    mcp.tool()(suppliers.cin7_get_supplier)
    mcp.tool()(suppliers.cin7_create_supplier)
    mcp.tool()(suppliers.cin7_update_supplier)

    # -- Tools: sales -------------------------------------------------------
    mcp.tool()(sales.cin7_sales)
    mcp.tool()(sales.cin7_get_sale)
    mcp.tool()(sales.cin7_create_sale)
    mcp.tool()(sales.cin7_update_sale)

    # -- Tools: purchase orders ---------------------------------------------
    mcp.tool()(purchase_orders.cin7_purchase_orders)
    mcp.tool()(purchase_orders.cin7_get_purchase_order)
    mcp.tool()(purchase_orders.cin7_create_purchase_order)

    # -- Tools: stock -------------------------------------------------------
    mcp.tool()(stock.cin7_stock_levels)
    mcp.tool()(stock.cin7_get_stock)
    mcp.tool()(stock.cin7_stock_transfers)
    mcp.tool()(stock.cin7_get_stock_transfer)

    # -- Tools: product snapshots -------------------------------------------
    mcp.tool()(snapshots.cin7_products_snapshot_start)
    mcp.tool()(snapshots.cin7_products_snapshot_status)
    mcp.tool()(snapshots.cin7_products_snapshot_chunk)
    mcp.tool()(snapshots.cin7_products_snapshot_close)

    # -- Tools: stock snapshots ---------------------------------------------
    mcp.tool()(snapshots.cin7_stock_snapshot_start)
    mcp.tool()(snapshots.cin7_stock_snapshot_status)
    mcp.tool()(snapshots.cin7_stock_snapshot_chunk)
    mcp.tool()(snapshots.cin7_stock_snapshot_close)

    # -- Resources ----------------------------------------------------------
    mcp.resource("cin7://templates/product")(templates.resource_product_template)
    mcp.resource("cin7://templates/product/{product_id}")(templates.resource_product_by_id)
    mcp.resource("cin7://templates/product/sku/{sku}")(templates.resource_product_by_sku)
    mcp.resource("cin7://templates/supplier")(templates.resource_supplier_template)
    mcp.resource("cin7://templates/supplier/{supplier_id}")(templates.resource_supplier_by_id)
    mcp.resource("cin7://templates/supplier/name/{name}")(templates.resource_supplier_by_name)
    mcp.resource("cin7://templates/purchase_order")(templates.resource_purchase_order_template)
    mcp.resource("cin7://templates/purchase_order/{purchase_order_id}")(templates.resource_purchase_order_by_id)
    mcp.resource("cin7://templates/sale")(templates.resource_sale_template)
    mcp.resource("cin7://templates/sale/{sale_id}")(templates.resource_sale_by_id)

    # -- Prompts ------------------------------------------------------------
    mcp.prompt()(prompts.create_product)
    mcp.prompt()(prompts.update_batch)
    mcp.prompt()(prompts.verify_required_fields)
    mcp.prompt()(prompts.create_purchase_order)
    mcp.prompt()(prompts.create_sale)

    return mcp


# Default server instance for stdio transport
server = create_mcp_server()
