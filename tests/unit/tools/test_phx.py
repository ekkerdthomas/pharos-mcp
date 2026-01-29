"""Tests for PhX API tools module."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pharos_mcp.core.phx_client import (
    PhxClient,
    PhxConnectionError,
    PhxError,
    PhxRateLimitError,
    PhxValidationError,
)
from pharos_mcp.tools.phx import _format_error, _format_response, register_phx_tools


class TestFormatHelpers:
    """Test formatting helper functions."""

    def test_format_error_basic(self) -> None:
        """_format_error should format basic error."""
        error = PhxError("Something went wrong")
        result = _format_error(error)

        assert "Something went wrong" in result

    def test_format_error_with_status_code(self) -> None:
        """_format_error should include status code."""
        error = PhxError("HTTP error", status_code=500)
        result = _format_error(error)

        assert "500" in result

    def test_format_error_with_syspro_errors(self) -> None:
        """_format_error should format SYSPRO errors."""
        error = PhxError(
            "Validation failed",
            status_code=400,
            syspro_errors=[
                {"field": "stockCode", "value": "INVALID", "message": "Stock not found"},
                {"field": "", "value": "", "message": "General error"},
            ],
        )
        result = _format_error(error)

        assert "SYSPRO Errors:" in result
        assert "stockCode" in result
        assert "Stock not found" in result
        assert "General error" in result

    def test_format_response_json(self) -> None:
        """_format_response should format data as JSON."""
        data = {"StockCode": "TEST001", "Description": "Test Item"}
        result = _format_response(data, "Inventory")

        assert "# Inventory" in result
        assert "```json" in result
        assert "TEST001" in result
        assert "Test Item" in result


class TestPhxToolsRegistration:
    """Test PhX tools registration."""

    def test_register_phx_tools_adds_tools(self) -> None:
        """register_phx_tools should add tools to MCP server."""
        mock_mcp = MagicMock()
        mock_mcp.tool = MagicMock(return_value=lambda f: f)

        register_phx_tools(mock_mcp)

        # Verify tool decorator was called multiple times
        assert mock_mcp.tool.call_count >= 8  # We have 8+ tools


class TestPhxTestConnection:
    """Test phx_test_connection tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.base_url = "http://test.local:5000"
        client.operator = "OP"
        client.company_id = "CO"
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_connection(self, mock_client: MagicMock) -> None:
        """Should return success message when connection works."""
        mock_client.test_connection = AsyncMock(return_value={"status": "healthy"})

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            # Import after patching
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_test_connection"]()

            assert "Connected" in result
            assert "http://test.local:5000" in result
            assert "healthy" in result

    @pytest.mark.asyncio
    async def test_not_configured(self) -> None:
        """Should return error when client not configured."""
        mock_client = MagicMock(spec=PhxClient)
        mock_client.is_configured = False

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_test_connection"]()

            assert "not configured" in result
            assert "PHX_URL" in result

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_client: MagicMock) -> None:
        """Should return error message when connection fails."""
        mock_client.test_connection = AsyncMock(
            side_effect=PhxConnectionError("Connection refused")
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_test_connection"]()

            assert "Failed" in result
            assert "Connection refused" in result


class TestPhxQueryInventory:
    """Test phx_query_inventory tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_query(self, mock_client: MagicMock) -> None:
        """Should return inventory data."""
        mock_client.query_inventory = AsyncMock(
            return_value={
                "StockCode": "TEST001",
                "Description": "Test Item",
                "QtyOnHand": 100,
            }
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_query_inventory"](stock_code="TEST001")

            assert "TEST001" in result
            assert "Test Item" in result
            mock_client.query_inventory.assert_called_once_with("TEST001")

    @pytest.mark.asyncio
    async def test_validation_error(self, mock_client: MagicMock) -> None:
        """Should return formatted error on validation failure."""
        mock_client.query_inventory = AsyncMock(
            side_effect=PhxValidationError(
                "Stock not found",
                status_code=400,
                syspro_errors=[{"field": "stockCode", "message": "Invalid stock code"}],
            )
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_query_inventory"](stock_code="INVALID")

            assert "Failed" in result
            assert "Invalid stock code" in result


class TestPhxQueryWipJob:
    """Test phx_query_wip_job tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_query(self, mock_client: MagicMock) -> None:
        """Should return job data."""
        mock_client.query_wip_job = AsyncMock(
            return_value={
                "Job": "J001",
                "StockCode": "TEST001",
                "QtyToMake": 100,
            }
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_query_wip_job"](
                job="J001", include_operations=True, include_materials=False
            )

            assert "J001" in result
            mock_client.query_wip_job.assert_called_once_with(
                "J001", include_operations=True, include_materials=False
            )


class TestPhxPostLabour:
    """Test phx_post_labour tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_post(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_labour = AsyncMock(
            return_value={"success": True, "journalNumber": "LAB001"}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_post_labour"](
                job="J001",
                operation="0010",
                work_centre="WC01",
                employee="EMP001",
                run_time_hours=2.5,
                qty_complete=10.0,
                oper_completed="N",
            )

            assert "Successfully" in result
            assert "J001" in result
            assert "2.5" in result
            mock_client.post_labour.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_error(self, mock_client: MagicMock) -> None:
        """Should return formatted error on validation failure."""
        mock_client.post_labour = AsyncMock(
            side_effect=PhxValidationError(
                "Invalid operation",
                status_code=400,
                syspro_errors=[{"field": "operation", "message": "Operation not found on job"}],
            )
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_post_labour"](
                job="J001",
                operation="9999",
                work_centre="WC01",
            )

            assert "Failed" in result
            assert "Operation not found" in result

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, mock_client: MagicMock) -> None:
        """Should return rate limit message."""
        mock_client.post_labour = AsyncMock(
            side_effect=PhxRateLimitError("Rate limit exceeded", status_code=429)
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_post_labour"](
                job="J001",
                operation="0010",
                work_centre="WC01",
            )

            assert "Rate Limit" in result


class TestPhxApproveRequisition:
    """Test phx_approve_requisition tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_approval(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.approve_requisition = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_approve_requisition"](
                user="APPROVER",
                requisition_number="REQ001",
            )

            assert "Approved" in result
            assert "REQ001" in result
            assert "APPROVER" in result


class TestPhxCallBusinessObject:
    """Test phx_call_business_object tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_call(self, mock_client: MagicMock) -> None:
        """Should return BO response."""
        mock_client.call_business_object = AsyncMock(
            return_value={"StockCode": "TEST001", "Description": "Test"}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_call_business_object"](
                bo_method="Query",
                business_object="INVQRY",
                xml_in="<Query><Key><StockCode>TEST001</StockCode></Key></Query>",
            )

            assert "Business Object Response" in result
            assert "INVQRY" in result
            assert "TEST001" in result
            mock_client.call_business_object.assert_called_once_with(
                bo_method="Query",
                business_object="INVQRY",
                xml_in="<Query><Key><StockCode>TEST001</StockCode></Key></Query>",
                xml_parameters="",
            )


class TestPhxWarehouseTransfer:
    """Test phx_warehouse_transfer tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_immediate_warehouse_transfer = AsyncMock(
            return_value={"success": True, "journal": "TRF001"}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_warehouse_transfer"](
                stock_code="TEST001",
                from_warehouse="WH1",
                to_warehouse="WH2",
                quantity=10.0,
                notation="Test transfer",
            )

            assert "Completed" in result
            assert "TEST001" in result
            assert "WH1" in result
            assert "WH2" in result
            mock_client.post_immediate_warehouse_transfer.assert_called_once()


class TestPhxBinTransfer:
    """Test phx_bin_transfer tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_bin_transfer = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_bin_transfer"](
                stock_code="TEST001",
                warehouse="WH1",
                from_bin="BIN1",
                to_bin="BIN2",
                quantity=5.0,
                notation="Bin transfer",
            )

            assert "Completed" in result
            assert "BIN1" in result
            assert "BIN2" in result


class TestPhxInventoryAdjustment:
    """Test phx_inventory_adjustment tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_adjustment(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_inventory_adjustment = AsyncMock(
            return_value={"success": True, "journal": "ADJ001"}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_inventory_adjustment"](
                stock_code="TEST001",
                warehouse="WH1",
                quantity=-5.0,
                notation="Cycle count",
            )

            assert "Completed" in result
            assert "Decrease" in result  # Negative quantity
            assert "5" in result

    @pytest.mark.asyncio
    async def test_positive_adjustment(self, mock_client: MagicMock) -> None:
        """Should show Increase for positive quantity."""
        mock_client.post_inventory_adjustment = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_inventory_adjustment"](
                stock_code="TEST001",
                warehouse="WH1",
                quantity=10.0,
                notation="Found stock",
            )

            assert "Increase" in result


class TestPhxExpenseIssue:
    """Test phx_expense_issue tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_issue(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_expense_issue = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_expense_issue"](
                stock_code="TEST001",
                warehouse="WH1",
                quantity=3.0,
                notation="Expense issue",
                ledger_code="6100-000",
            )

            assert "Completed" in result
            assert "6100-000" in result


class TestPhxGitTransferOut:
    """Test phx_git_transfer_out tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_client: MagicMock) -> None:
        """Should return success message with follow-up instructions."""
        mock_client.post_git_transfer_out = AsyncMock(
            return_value={"success": True, "gitReference": "GIT001"}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_git_transfer_out"](
                stock_code="TEST001",
                from_warehouse="WH1",
                to_warehouse="WH2",
                quantity=20.0,
                notation="GIT transfer",
            )

            assert "Initiated" in result
            assert "phx_git_transfer_in" in result  # Follow-up instructions


class TestPhxGitTransferIn:
    """Test phx_git_transfer_in tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_git_transfer_in = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_git_transfer_in"](
                stock_code="TEST001",
                warehouse="WH2",
                quantity=20.0,
                notation="GIT receive",
            )

            assert "Completed" in result


class TestPhxTransferOut:
    """Test phx_transfer_out tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_client: MagicMock) -> None:
        """Should return success message with follow-up instructions."""
        mock_client.post_warehouse_transfer_out = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_transfer_out"](
                stock_code="TEST001",
                from_warehouse="WH1",
                to_warehouse="WH2",
                quantity=15.0,
                notation="Transfer out",
            )

            assert "Initiated" in result
            assert "phx_transfer_in" in result  # Follow-up instructions


class TestPhxTransferIn:
    """Test phx_transfer_in tool."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock PhxClient."""
        client = MagicMock(spec=PhxClient)
        client.is_configured = True
        return client

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_client: MagicMock) -> None:
        """Should return success message."""
        mock_client.post_warehouse_transfer_in = AsyncMock(
            return_value={"success": True}
        )

        with patch("pharos_mcp.tools.phx.get_phx_client", return_value=mock_client):
            from pharos_mcp.tools.phx import register_phx_tools

            mock_mcp = MagicMock()
            tools: dict[str, Any] = {}

            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator

            mock_mcp.tool = capture_tool
            register_phx_tools(mock_mcp)

            result = await tools["phx_transfer_in"](
                stock_code="TEST001",
                warehouse="WH2",
                quantity=15.0,
                notation="Transfer in",
            )

            assert "Completed" in result


class TestPhxToolsRegistrationCount:
    """Test that all PhX tools are registered."""

    def test_all_tools_registered(self) -> None:
        """register_phx_tools should add all 16+ tools to MCP server."""
        mock_mcp = MagicMock()
        mock_mcp.tool = MagicMock(return_value=lambda f: f)

        register_phx_tools(mock_mcp)

        # We now have 8 original tools + 8 new inventory movement tools = 16
        assert mock_mcp.tool.call_count >= 16
