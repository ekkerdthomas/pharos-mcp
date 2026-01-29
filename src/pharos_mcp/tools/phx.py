"""
PhX API tools for Pharos MCP.

Provides MCP tools for interacting with SYSPRO via the PhX REST API.
Enables both query (read) and transaction (write) operations.

Tools:
- phx_test_connection: Health check
- phx_query_inventory: Inventory lookup
- phx_query_wip_job: Job details
- phx_post_labour: Post labour transactions
- phx_post_job_receipt: Complete jobs
- phx_post_material: Issue materials
- phx_approve_requisition: Approve PRs
- phx_call_business_object: Generic BO gateway
"""

import json
import logging

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.phx_client import (
    PhxClient,
    PhxConnectionError,
    PhxError,
    PhxRateLimitError,
    PhxValidationError,
    get_phx_client,
)

logger = logging.getLogger(__name__)


def _format_error(error: PhxError) -> str:
    """Format PhX error for MCP response.

    Args:
        error: PhX exception

    Returns:
        Formatted error message
    """
    lines = [f"Error: {error}"]

    if error.status_code:
        lines.append(f"Status: {error.status_code}")

    if error.syspro_errors:
        lines.append("\nSYSPRO Errors:")
        for err in error.syspro_errors:
            if err.get("field"):
                lines.append(f"  - {err['field']}: {err['message']}")
            else:
                lines.append(f"  - {err['message']}")

    return "\n".join(lines)


def _format_response(data: dict, title: str = "Result") -> str:
    """Format successful response for MCP.

    Args:
        data: Response data
        title: Section title

    Returns:
        Formatted response string
    """
    return f"# {title}\n\n```json\n{json.dumps(data, indent=2)}\n```"


def register_phx_tools(mcp: FastMCP) -> None:
    """Register PhX API tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
    """

    @mcp.tool()
    @audit_tool_call("phx_test_connection")
    async def phx_test_connection() -> str:
        """Test connectivity to the PhX API.

        Verifies that the PhX REST API is accessible and responding.
        Use this to diagnose connection issues before running other PhX tools.

        Returns:
            Connection status and API health information.
        """
        client = get_phx_client()

        if not client.is_configured:
            return (
                "Error: PhX client not configured.\n\n"
                "Required environment variables:\n"
                "- PHX_URL: PhX API base URL (e.g., http://localhost:5000)\n"
                "- PHX_OPERATOR: SYSPRO operator code\n"
                "- PHX_COMPANY_ID: SYSPRO company ID"
            )

        try:
            result = await client.test_connection()
            return (
                "# PhX Connection Status\n\n"
                f"**Status**: Connected\n"
                f"**URL**: {client.base_url}\n"
                f"**Operator**: {client.operator}\n"
                f"**Company**: {client.company_id}\n\n"
                f"Health check response:\n```json\n{json.dumps(result, indent=2)}\n```"
            )
        except PhxConnectionError as e:
            return (
                "# PhX Connection Status\n\n"
                f"**Status**: Failed\n"
                f"**URL**: {client.base_url}\n\n"
                f"Error: {e}\n\n"
                "Check that:\n"
                "1. PhX API is running at the configured URL\n"
                "2. Network connectivity is available\n"
                "3. PHX_URL environment variable is correct"
            )
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_query_inventory")
    async def phx_query_inventory(stock_code: str) -> str:
        """Query inventory information for a stock code.

        Retrieves detailed inventory data from SYSPRO including:
        - Stock description and details
        - Warehouse quantities
        - Costs and pricing
        - Lot/serial information (if applicable)

        Args:
            stock_code: SYSPRO stock code to query.

        Returns:
            Inventory details in JSON format, or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.query_inventory(stock_code)
            return _format_response(result, f"Inventory: {stock_code}")
        except PhxValidationError as e:
            return (
                f"# Inventory Query Failed\n\n"
                f"Stock code: {stock_code}\n\n"
                f"{_format_error(e)}"
            )
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_query_wip_job")
    async def phx_query_wip_job(
        job: str,
        include_operations: bool = True,
        include_materials: bool = True,
    ) -> str:
        """Query WIP job details from SYSPRO.

        Retrieves comprehensive job information including:
        - Job header (stock code, quantities, status)
        - Operations (routing, work centres, times)
        - Materials (BOM, allocations, issues)
        - Transactions history

        Args:
            job: SYSPRO job number.
            include_operations: Include operation details and transactions.
            include_materials: Include material details and transactions.

        Returns:
            Job details in JSON format, or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.query_wip_job(
                job,
                include_operations=include_operations,
                include_materials=include_materials,
            )
            return _format_response(result, f"WIP Job: {job}")
        except PhxValidationError as e:
            return f"# WIP Job Query Failed\n\nJob: {job}\n\n{_format_error(e)}"
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_query_wip_tracking")
    async def phx_query_wip_tracking(job: str) -> str:
        """Query WIP job tracking and variance information.

        Retrieves variance analysis for a job including:
        - Labour variances (actual vs standard)
        - Material variances
        - Overhead variances
        - Cost summaries

        Args:
            job: SYSPRO job number.

        Returns:
            Tracking/variance data in JSON format, or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.query_wip_tracking(job)
            return _format_response(result, f"WIP Tracking: {job}")
        except PhxValidationError as e:
            return f"# WIP Tracking Query Failed\n\nJob: {job}\n\n{_format_error(e)}"
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_query_requisition")
    async def phx_query_requisition(
        user: str,
        user_password: str = "",
        requisition_number: str = "",
        include_approved: str = "Y",
    ) -> str:
        """Query requisitions for a user.

        Retrieves purchase requisition data including:
        - Requisition header information
        - Line items with stock codes, quantities, prices
        - Approval status and routing
        - Associated purchase orders

        Args:
            user: SYSPRO requisition user.
            user_password: User password (if required by SYSPRO setup).
            requisition_number: Specific requisition number (optional).
            include_approved: Include approved requisitions (Y/N).

        Returns:
            Requisition data in JSON format, or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.query_requisition(
                user,
                user_password=user_password,
                requisition_number=requisition_number,
                include_approved=include_approved,
            )
            title = f"Requisitions: {user}"
            if requisition_number:
                title = f"Requisition: {requisition_number}"
            return _format_response(result, title)
        except PhxValidationError as e:
            return f"# Requisition Query Failed\n\nUser: {user}\n\n{_format_error(e)}"
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_post_labour")
    async def phx_post_labour(
        job: str,
        operation: str,
        work_centre: str,
        employee: str = "",
        run_time_hours: float = 0.0,
        qty_complete: float = 0.0,
        oper_completed: str = "N",
        reference: str = "",
    ) -> str:
        """Post labour to a job operation in SYSPRO.

        Records labour time and/or quantity against a job operation.
        This is a WRITE operation that modifies SYSPRO data.

        Args:
            job: SYSPRO job number.
            operation: Operation number (e.g., "0010", "0020").
            work_centre: Work centre code.
            employee: Employee code (optional, uses default if empty).
            run_time_hours: Run time in hours (decimal).
            qty_complete: Quantity completed.
            oper_completed: Mark operation as completed (Y/N).
            reference: Transaction reference (max 30 chars).

        Returns:
            Transaction result or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.post_labour(
                job=job,
                operation=operation,
                work_centre=work_centre,
                employee=employee,
                run_time_hours=run_time_hours,
                qty_complete=qty_complete,
                oper_completed=oper_completed,
                reference=reference,
            )
            return (
                f"# Labour Posted Successfully\n\n"
                f"**Job**: {job}\n"
                f"**Operation**: {operation}\n"
                f"**Work Centre**: {work_centre}\n"
                f"**Run Time**: {run_time_hours} hours\n"
                f"**Qty Complete**: {qty_complete}\n"
                f"**Operation Completed**: {oper_completed}\n\n"
                f"```json\n{json.dumps(result, indent=2)}\n```"
            )
        except PhxValidationError as e:
            return (
                f"# Labour Post Failed\n\n"
                f"Job: {job}, Operation: {operation}\n\n"
                f"{_format_error(e)}"
            )
        except PhxRateLimitError as e:
            return f"# Rate Limit Exceeded\n\n{e}\n\nWait and retry."
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_post_job_receipt")
    async def phx_post_job_receipt(
        job: str,
        qty_to_manufacture: float,
        receipt_qty: float,
        warehouse: str,
        unit_cost: float | None = None,
        reference: str = "",
    ) -> str:
        """Post job receipt (complete manufactured items) in SYSPRO.

        Receives completed goods from a manufacturing job into inventory.
        This is a WRITE operation that modifies SYSPRO data.

        Args:
            job: SYSPRO job number.
            qty_to_manufacture: Total quantity to manufacture.
            receipt_qty: Quantity being received (may be partial).
            warehouse: Destination warehouse for receipts.
            unit_cost: Override unit cost (optional, uses job cost if not specified).
            reference: Transaction reference.

        Returns:
            Transaction result or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.post_job_receipt(
                job=job,
                qty_to_manufacture=qty_to_manufacture,
                receipt_qty=receipt_qty,
                warehouse=warehouse,
                unit_cost=unit_cost,
                reference=reference,
            )
            return (
                f"# Job Receipt Posted Successfully\n\n"
                f"**Job**: {job}\n"
                f"**Qty Manufactured**: {qty_to_manufacture}\n"
                f"**Receipt Qty**: {receipt_qty}\n"
                f"**Warehouse**: {warehouse}\n\n"
                f"```json\n{json.dumps(result, indent=2)}\n```"
            )
        except PhxValidationError as e:
            return f"# Job Receipt Failed\n\nJob: {job}\n\n{_format_error(e)}"
        except PhxRateLimitError as e:
            return f"# Rate Limit Exceeded\n\n{e}\n\nWait and retry."
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_post_material")
    async def phx_post_material(
        job: str,
        stock_code: str,
        warehouse: str,
        qty_issued: float,
        bin_location: str,
        alloc_completed: str = "N",
        reference: str = "",
    ) -> str:
        """Post material issue to a job in SYSPRO.

        Issues material from inventory to a manufacturing job.
        This is a WRITE operation that modifies SYSPRO data.

        Args:
            job: SYSPRO job number.
            stock_code: Stock code to issue.
            warehouse: Source warehouse.
            qty_issued: Quantity to issue.
            bin_location: Source bin location.
            alloc_completed: Mark allocation as completed (Y/N).
            reference: Transaction reference.

        Returns:
            Transaction result or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.post_material(
                job=job,
                stock_code=stock_code,
                warehouse=warehouse,
                qty_issued=qty_issued,
                bin_location=bin_location,
                alloc_completed=alloc_completed,
                reference=reference,
            )
            return (
                f"# Material Posted Successfully\n\n"
                f"**Job**: {job}\n"
                f"**Stock Code**: {stock_code}\n"
                f"**Warehouse**: {warehouse}\n"
                f"**Qty Issued**: {qty_issued}\n"
                f"**Bin**: {bin_location}\n\n"
                f"```json\n{json.dumps(result, indent=2)}\n```"
            )
        except PhxValidationError as e:
            return (
                f"# Material Post Failed\n\n"
                f"Job: {job}, Stock: {stock_code}\n\n"
                f"{_format_error(e)}"
            )
        except PhxRateLimitError as e:
            return f"# Rate Limit Exceeded\n\n{e}\n\nWait and retry."
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_approve_requisition")
    async def phx_approve_requisition(
        user: str,
        requisition_number: str,
        user_password: str = "",
        requisition_line: str = "",
    ) -> str:
        """Approve a purchase requisition in SYSPRO.

        Approves a requisition or specific line for purchasing.
        This is a WRITE operation that modifies SYSPRO data.

        Args:
            user: Approving user code.
            requisition_number: Requisition number to approve.
            user_password: User password (if required by SYSPRO).
            requisition_line: Specific line to approve (optional, approves all if empty).

        Returns:
            Approval result or error message.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.approve_requisition(
                user=user,
                requisition_number=requisition_number,
                user_password=user_password,
                requisition_line=requisition_line,
            )
            line_info = f" Line {requisition_line}" if requisition_line else " (all lines)"
            return (
                f"# Requisition Approved\n\n"
                f"**Requisition**: {requisition_number}{line_info}\n"
                f"**Approved By**: {user}\n\n"
                f"```json\n{json.dumps(result, indent=2)}\n```"
            )
        except PhxValidationError as e:
            return (
                f"# Requisition Approval Failed\n\n"
                f"Requisition: {requisition_number}\n"
                f"User: {user}\n\n"
                f"{_format_error(e)}"
            )
        except PhxRateLimitError as e:
            return f"# Rate Limit Exceeded\n\n{e}\n\nWait and retry."
        except PhxError as e:
            return _format_error(e)

    @mcp.tool()
    @audit_tool_call("phx_call_business_object")
    async def phx_call_business_object(
        bo_method: str,
        business_object: str,
        xml_in: str,
        xml_parameters: str = "",
    ) -> str:
        """Call a SYSPRO business object directly via PhX.

        Generic gateway for any SYSPRO business object not covered by specific tools.
        Requires knowledge of SYSPRO BO XML formats.

        Common bo_method values:
        - "Query": Read data (e.g., INVQRY, WIPQRY)
        - "Post": Write transactions (e.g., WIPTLP, WIPTJR)
        - "Build": Build transactions (e.g., SORTBO)
        - "Setup": Setup operations

        Args:
            bo_method: Business object method (Query, Post, Build, Setup).
            business_object: Business object name (e.g., INVQRY, WIPTLP).
            xml_in: Input XML for the business object.
            xml_parameters: Parameters XML (optional).

        Returns:
            Business object response or error message.

        Note: This tool requires understanding of SYSPRO business objects.
        Prefer using specific tools (phx_query_inventory, phx_post_labour, etc.)
        when available.
        """
        client = get_phx_client()

        if not client.is_configured:
            return "Error: PhX client not configured. Run phx_test_connection for details."

        try:
            result = await client.call_business_object(
                bo_method=bo_method,
                business_object=business_object,
                xml_in=xml_in,
                xml_parameters=xml_parameters,
            )
            return (
                f"# Business Object Response\n\n"
                f"**Method**: {bo_method}\n"
                f"**BO**: {business_object}\n\n"
                f"```json\n{json.dumps(result, indent=2)}\n```"
            )
        except PhxValidationError as e:
            return (
                f"# Business Object Call Failed\n\n"
                f"Method: {bo_method}, BO: {business_object}\n\n"
                f"{_format_error(e)}"
            )
        except PhxRateLimitError as e:
            return f"# Rate Limit Exceeded\n\n{e}\n\nWait and retry."
        except PhxError as e:
            return _format_error(e)
