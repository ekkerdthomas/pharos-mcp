"""Tests for PhX API client module."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pharos_mcp.core.phx_client import (
    PhxClient,
    PhxConnectionError,
    PhxError,
    PhxRateLimitError,
    PhxValidationError,
    get_phx_client,
    reset_phx_client,
)


class TestPhxClientInitialization:
    """Test PhxClient initialization and configuration."""

    def test_init_with_explicit_params(self) -> None:
        """Client should accept explicit parameters."""
        client = PhxClient(
            base_url="http://test.local:5000",
            operator="TEST_OP",
            operator_password="test_pass",
            company_id="TEST_CO",
            company_password="co_pass",
            timeout=60.0,
            max_retries=3,
        )

        assert client.base_url == "http://test.local:5000"
        assert client.operator == "TEST_OP"
        assert client.operator_password == "test_pass"
        assert client.company_id == "TEST_CO"
        assert client.company_password == "co_pass"
        assert client.timeout == 60.0
        assert client.max_retries == 3

    def test_init_strips_trailing_slash(self) -> None:
        """Base URL should have trailing slash stripped."""
        client = PhxClient(base_url="http://test.local:5000/")
        assert client.base_url == "http://test.local:5000"

    def test_init_from_env_vars(self) -> None:
        """Client should read from environment variables."""
        env_vars = {
            "PHX_URL": "http://env.local:5000",
            "PHX_OPERATOR": "ENV_OP",
            "PHX_OPERATOR_PASSWORD": "env_pass",
            "PHX_COMPANY_ID": "ENV_CO",
            "PHX_COMPANY_PASSWORD": "env_co_pass",
        }

        with patch.dict("os.environ", env_vars, clear=False):
            client = PhxClient()

            assert client.base_url == "http://env.local:5000"
            assert client.operator == "ENV_OP"
            assert client.operator_password == "env_pass"
            assert client.company_id == "ENV_CO"
            assert client.company_password == "env_co_pass"

    def test_is_configured_true_when_complete(self) -> None:
        """is_configured should be True when required fields are set."""
        client = PhxClient(
            base_url="http://test.local:5000",
            operator="OP",
            company_id="CO",
        )
        assert client.is_configured is True

    def test_is_configured_false_when_missing_url(self) -> None:
        """is_configured should be False when URL is missing."""
        client = PhxClient(operator="OP", company_id="CO")
        assert client.is_configured is False

    def test_is_configured_false_when_missing_operator(self) -> None:
        """is_configured should be False when operator is missing."""
        client = PhxClient(base_url="http://test.local:5000", company_id="CO")
        assert client.is_configured is False

    def test_is_configured_false_when_missing_company(self) -> None:
        """is_configured should be False when company is missing."""
        client = PhxClient(base_url="http://test.local:5000", operator="OP")
        assert client.is_configured is False


class TestPhxClientAuth:
    """Test PhxClient authentication handling."""

    def test_add_auth_adds_credentials(self) -> None:
        """_add_auth should add DirectAuth credentials to request."""
        client = PhxClient(
            base_url="http://test.local:5000",
            operator="OP",
            operator_password="op_pass",
            company_id="CO",
            company_password="co_pass",
        )

        data = {"stockCode": "TEST001"}
        result = client._add_auth(data)

        assert result["operator"] == "OP"
        assert result["operatorPassword"] == "op_pass"
        assert result["companyId"] == "CO"
        assert result["companyPassword"] == "co_pass"
        assert result["stockCode"] == "TEST001"

    def test_add_auth_preserves_existing_data(self) -> None:
        """_add_auth should not overwrite existing request data."""
        client = PhxClient(
            base_url="http://test.local:5000",
            operator="OP",
            company_id="CO",
        )

        data = {"job": "J001", "operation": "0010"}
        result = client._add_auth(data)

        assert result["job"] == "J001"
        assert result["operation"] == "0010"


class TestPhxClientErrorExtraction:
    """Test SYSPRO error extraction from responses."""

    def test_extract_errors_from_errors_list(self) -> None:
        """Should extract errors from 'errors' array."""
        response = {
            "success": False,
            "errors": [
                {"field": "stockCode", "value": "INVALID", "message": "Stock not found"},
                {"field": "qty", "message": "Quantity must be positive"},
            ],
        }

        errors = PhxClient.extract_syspro_errors(response)

        assert len(errors) == 2
        assert errors[0]["field"] == "stockCode"
        assert errors[0]["value"] == "INVALID"
        assert errors[0]["message"] == "Stock not found"
        assert errors[1]["field"] == "qty"
        assert errors[1]["message"] == "Quantity must be positive"

    def test_extract_errors_from_validation_errors(self) -> None:
        """Should extract errors from 'validationErrors' array."""
        response = {
            "Success": False,
            "ValidationErrors": [
                {"Field": "Job", "Value": "", "ErrorMessage": "Job is required"},
            ],
        }

        errors = PhxClient.extract_syspro_errors(response)

        assert len(errors) == 1
        assert errors[0]["field"] == "Job"
        assert errors[0]["message"] == "Job is required"

    def test_extract_errors_from_message(self) -> None:
        """Should extract error from 'message' field when success is False."""
        response = {
            "success": False,
            "message": "Operation failed due to invalid input",
        }

        errors = PhxClient.extract_syspro_errors(response)

        assert len(errors) == 1
        assert errors[0]["message"] == "Operation failed due to invalid input"

    def test_extract_errors_from_error_type(self) -> None:
        """Should extract error from errorType/errorDetails."""
        response = {
            "success": False,
            "errorType": "validation_error",
            "errorDetails": "Stock code does not exist",
        }

        errors = PhxClient.extract_syspro_errors(response)

        assert len(errors) == 1
        assert errors[0]["field"] == "validation_error"
        assert errors[0]["message"] == "Stock code does not exist"

    def test_extract_errors_from_string_response(self) -> None:
        """Should extract errors from string response."""
        response = "Error: Connection to SYSPRO failed\nErrorMessage: Service unavailable"

        errors = PhxClient.extract_syspro_errors(response)

        assert len(errors) >= 1
        assert any("Connection to SYSPRO failed" in e["message"] for e in errors)

    def test_extract_errors_empty_for_success(self) -> None:
        """Should return empty list for successful response."""
        response = {"success": True, "data": {"stockCode": "TEST001"}}

        errors = PhxClient.extract_syspro_errors(response)

        assert errors == []

    def test_extract_errors_handles_string_errors(self) -> None:
        """Should handle errors array with string items."""
        response = {
            "success": False,
            "errors": ["Error 1", "Error 2"],
        }

        errors = PhxClient.extract_syspro_errors(response)

        assert len(errors) == 2
        assert errors[0]["message"] == "Error 1"
        assert errors[1]["message"] == "Error 2"


class TestPhxClientRequests:
    """Test PhxClient HTTP request handling."""

    @pytest.fixture
    def client(self) -> PhxClient:
        """Create a configured PhxClient for testing."""
        return PhxClient(
            base_url="http://test.local:5000",
            operator="TEST_OP",
            operator_password="test_pass",
            company_id="TEST_CO",
            company_password="co_pass",
            timeout=5.0,
            max_retries=2,
            retry_delay=0.1,
        )

    @pytest.mark.asyncio
    async def test_successful_get_request(self, client: PhxClient) -> None:
        """Should handle successful GET request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.text = '{"status": "healthy"}'

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client._request("GET", "/health", add_auth=False)

            assert result == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_successful_post_request(self, client: PhxClient) -> None:
        """Should handle successful POST request with auth."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"StockCode": "TEST001", "Description": "Test Item"}
        mock_response.text = '{"StockCode": "TEST001"}'

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await client._request("POST", "/api/QueryBo/inventory", {"stockCode": "TEST001"})

            assert result["StockCode"] == "TEST001"
            # Verify auth was added
            call_kwargs = mock_post.call_args
            assert call_kwargs.kwargs["json"]["operator"] == "TEST_OP"
            assert call_kwargs.kwargs["json"]["companyId"] == "TEST_CO"

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, client: PhxClient) -> None:
        """Should raise PhxRateLimitError on 429 response."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"message": "Rate limit exceeded"}
        mock_response.text = '{"message": "Rate limit exceeded"}'

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(PhxRateLimitError) as exc_info:
                await client._request("POST", "/api/test", {})

            assert exc_info.value.status_code == 429
            assert "60" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_error(self, client: PhxClient) -> None:
        """Should raise PhxValidationError on 400 response."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "success": False,
            "message": "Stock code not found",
            "errors": [{"field": "stockCode", "message": "Invalid stock code"}],
        }
        mock_response.text = '{"success": false}'

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(PhxValidationError) as exc_info:
                await client._request("POST", "/api/test", {})

            assert exc_info.value.status_code == 400
            assert len(exc_info.value.syspro_errors) >= 1

    @pytest.mark.asyncio
    async def test_connection_error_with_retry(self, client: PhxClient) -> None:
        """Should retry on connection error and eventually raise."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(PhxConnectionError) as exc_info:
                await client._request("POST", "/api/test", {})

            assert "Connection" in str(exc_info.value)
            # Should have retried (max_retries=2, so 3 total attempts)
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_error_with_retry(self, client: PhxClient) -> None:
        """Should retry on timeout and eventually raise."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(PhxConnectionError) as exc_info:
                await client._request("POST", "/api/test", {})

            assert "timeout" in str(exc_info.value).lower()
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_success_false_in_response(self, client: PhxClient) -> None:
        """Should raise PhxValidationError when response has success=false."""
        mock_response = MagicMock()
        mock_response.status_code = 200  # HTTP success but SYSPRO error
        mock_response.json.return_value = {
            "success": False,
            "message": "SYSPRO validation failed",
        }
        mock_response.text = '{"success": false}'

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(PhxValidationError) as exc_info:
                await client._request("POST", "/api/test", {})

            assert "SYSPRO validation failed" in str(exc_info.value)


class TestPhxClientMethods:
    """Test PhxClient business methods."""

    @pytest.fixture
    def client(self) -> PhxClient:
        """Create a configured PhxClient for testing."""
        return PhxClient(
            base_url="http://test.local:5000",
            operator="OP",
            company_id="CO",
        )

    @pytest.mark.asyncio
    async def test_test_connection(self, client: PhxClient) -> None:
        """test_connection should call health endpoint without auth."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"status": "healthy"}

            result = await client.test_connection()

            mock_request.assert_called_once_with("GET", "/health", add_auth=False)
            assert result == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_query_inventory(self, client: PhxClient) -> None:
        """query_inventory should POST to inventory endpoint."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"StockCode": "TEST001"}

            result = await client.query_inventory("TEST001")

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args.args[0] == "POST"
            assert "/inventory" in call_args.args[1]
            assert call_args.args[2]["stockCode"] == "TEST001"

    @pytest.mark.asyncio
    async def test_query_wip_job(self, client: PhxClient) -> None:
        """query_wip_job should POST with job number and options."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"Job": "J001"}

            result = await client.query_wip_job(
                "J001", include_operations=True, include_materials=False
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            assert data["job"] == "J001"
            assert data["includeOperationAllocations"] == "Y"
            assert data["includeMaterialAllocations"] == "N"

    @pytest.mark.asyncio
    async def test_post_labour(self, client: PhxClient) -> None:
        """post_labour should POST labour transaction."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_labour(
                job="J001",
                operation="0010",
                work_centre="WC01",
                employee="EMP001",
                run_time_hours=2.5,
                qty_complete=10.0,
                oper_completed="N",
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            assert data["job"] == "J001"
            assert data["lOperation"] == "0010"
            assert data["lWorkCentre"] == "WC01"
            assert data["lEmployee"] == "EMP001"
            assert data["lRunTimeHours"] == "2.5"
            assert data["lQtyComplete"] == "10.0"
            assert data["operCompleted"] == "N"

    @pytest.mark.asyncio
    async def test_post_job_receipt(self, client: PhxClient) -> None:
        """post_job_receipt should POST job receipt transaction."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_job_receipt(
                job="J001",
                qty_to_manufacture=100.0,
                receipt_qty=50.0,
                warehouse="WH01",
                unit_cost=25.50,
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            assert data["job"] == "J001"
            assert data["qtyToManufacture"] == "100.0"
            assert data["receiptQty"] == "50.0"
            assert data["warehouse"] == "WH01"
            assert data["unitCost"] == "25.5"

    @pytest.mark.asyncio
    async def test_approve_requisition(self, client: PhxClient) -> None:
        """approve_requisition should POST approval request."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.approve_requisition(
                user="APPROVER",
                requisition_number="REQ001",
                user_password="pass",
                requisition_line="1",
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            assert data["user"] == "APPROVER"
            assert data["requisitionNumber"] == "REQ001"
            assert data["userPassword"] == "pass"
            assert data["requisitionLine"] == "1"


class TestPhxClientSingleton:
    """Test PhxClient singleton management."""

    def test_get_phx_client_returns_singleton(self) -> None:
        """get_phx_client should return the same instance."""
        reset_phx_client()

        client1 = get_phx_client()
        client2 = get_phx_client()

        assert client1 is client2

    def test_reset_phx_client_clears_singleton(self) -> None:
        """reset_phx_client should clear the singleton."""
        client1 = get_phx_client()
        reset_phx_client()
        client2 = get_phx_client()

        assert client1 is not client2


class TestPhxExceptions:
    """Test PhX exception classes."""

    def test_phx_error_with_all_fields(self) -> None:
        """PhxError should store all provided fields."""
        error = PhxError(
            "Test error",
            status_code=500,
            syspro_errors=[{"field": "test", "message": "error"}],
            raw_response="<xml>...</xml>",
        )

        assert str(error) == "Test error"
        assert error.status_code == 500
        assert len(error.syspro_errors) == 1
        assert error.raw_response == "<xml>...</xml>"

    def test_phx_error_with_defaults(self) -> None:
        """PhxError should have sensible defaults."""
        error = PhxError("Simple error")

        assert str(error) == "Simple error"
        assert error.status_code is None
        assert error.syspro_errors == []
        assert error.raw_response is None

    def test_phx_connection_error_is_phx_error(self) -> None:
        """PhxConnectionError should be a PhxError subclass."""
        error = PhxConnectionError("Connection failed")
        assert isinstance(error, PhxError)

    def test_phx_rate_limit_error_is_phx_error(self) -> None:
        """PhxRateLimitError should be a PhxError subclass."""
        error = PhxRateLimitError("Rate limited", status_code=429)
        assert isinstance(error, PhxError)
        assert error.status_code == 429

    def test_phx_validation_error_is_phx_error(self) -> None:
        """PhxValidationError should be a PhxError subclass."""
        error = PhxValidationError(
            "Validation failed",
            status_code=400,
            syspro_errors=[{"message": "Invalid input"}],
        )
        assert isinstance(error, PhxError)
        assert error.status_code == 400


class TestPhxClientInventoryMovements:
    """Test PhxClient inventory movement methods."""

    @pytest.fixture
    def client(self) -> PhxClient:
        """Create a configured PhxClient for testing."""
        return PhxClient(
            base_url="http://test.local:5000",
            operator="OP",
            company_id="CO",
        )

    @pytest.mark.asyncio
    async def test_post_immediate_warehouse_transfer(self, client: PhxClient) -> None:
        """post_immediate_warehouse_transfer should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True, "journal": "TRF001"}

            result = await client.post_immediate_warehouse_transfer(
                stock_code="TEST001",
                from_warehouse="WH1",
                to_warehouse="WH2",
                quantity=10.0,
                notation="Test transfer",
                from_bin="BIN1",
                to_bin="BIN2",
                reference="REF001",
            )

            call_args = mock_request.call_args
            assert call_args.args[0] == "POST"
            assert "/api/InvMovements/post-immediate-warehouse-transfer" in call_args.args[1]
            data = call_args.args[2]
            assert "items" in data
            assert len(data["items"]) == 1
            item = data["items"][0]
            assert item["stockCode"] == "TEST001"
            assert item["fromWarehouse"] == "WH1"
            assert item["toWarehouse"] == "WH2"
            assert item["quantity"] == "10.0"  # Should be string
            assert item["notation"] == "Test transfer"
            assert item["fromBin"] == "BIN1"
            assert item["toBin"] == "BIN2"
            assert item["reference"] == "REF001"

    @pytest.mark.asyncio
    async def test_post_bin_transfer(self, client: PhxClient) -> None:
        """post_bin_transfer should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_bin_transfer(
                stock_code="TEST001",
                warehouse="WH1",
                from_bin="BIN1",
                to_bin="BIN2",
                quantity=5.0,
                notation="Bin transfer",
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            item = data["items"][0]
            assert item["stockCode"] == "TEST001"
            assert item["warehouse"] == "WH1"
            assert item["fromBin"] == "BIN1"
            assert item["toBin"] == "BIN2"
            assert item["quantity"] == "5.0"
            assert item["notation"] == "Bin transfer"

    @pytest.mark.asyncio
    async def test_post_inventory_adjustment(self, client: PhxClient) -> None:
        """post_inventory_adjustment should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_inventory_adjustment(
                stock_code="TEST001",
                warehouse="WH1",
                quantity=-5.0,
                notation="Cycle count adjustment",
                bin_location="BIN1",
                unit_cost=10.50,
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            item = data["items"][0]
            assert item["stockCode"] == "TEST001"
            assert item["warehouse"] == "WH1"
            assert item["quantity"] == "-5.0"
            assert item["notation"] == "Cycle count adjustment"
            assert item["bin"] == "BIN1"
            assert item["unitCost"] == "10.5"

    @pytest.mark.asyncio
    async def test_post_expense_issue(self, client: PhxClient) -> None:
        """post_expense_issue should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_expense_issue(
                stock_code="TEST001",
                warehouse="WH1",
                quantity=3.0,
                notation="Expense issue",
                ledger_code="6100-000",
            )

            call_args = mock_request.call_args
            data = call_args.args[2]
            item = data["items"][0]
            assert item["stockCode"] == "TEST001"
            assert item["warehouse"] == "WH1"
            assert item["quantity"] == "3.0"
            assert item["notation"] == "Expense issue"
            assert item["ledgerCode"] == "6100-000"

    @pytest.mark.asyncio
    async def test_post_git_transfer_out(self, client: PhxClient) -> None:
        """post_git_transfer_out should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True, "gitReference": "GIT001"}

            result = await client.post_git_transfer_out(
                stock_code="TEST001",
                from_warehouse="WH1",
                to_warehouse="WH2",
                quantity=20.0,
                notation="GIT transfer out",
            )

            call_args = mock_request.call_args
            assert "/api/InvMovements/post-git-warehouse-transfer-out" in call_args.args[1]
            data = call_args.args[2]
            item = data["items"][0]
            assert item["stockCode"] == "TEST001"
            assert item["fromWarehouse"] == "WH1"
            assert item["toWarehouse"] == "WH2"
            assert item["quantity"] == "20.0"

    @pytest.mark.asyncio
    async def test_post_git_transfer_in(self, client: PhxClient) -> None:
        """post_git_transfer_in should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_git_transfer_in(
                stock_code="TEST001",
                warehouse="WH2",
                quantity=20.0,
                notation="GIT transfer in",
            )

            call_args = mock_request.call_args
            assert "/api/InvMovements/post-git-warehouse-transfer-in" in call_args.args[1]
            data = call_args.args[2]
            item = data["items"][0]
            assert item["stockCode"] == "TEST001"
            assert item["warehouse"] == "WH2"
            assert item["quantity"] == "20.0"

    @pytest.mark.asyncio
    async def test_post_warehouse_transfer_out(self, client: PhxClient) -> None:
        """post_warehouse_transfer_out should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_warehouse_transfer_out(
                stock_code="TEST001",
                from_warehouse="WH1",
                to_warehouse="WH2",
                quantity=15.0,
                notation="Transfer out",
            )

            call_args = mock_request.call_args
            assert "/api/InvMovements/post-warehouse-transfer-out" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_post_warehouse_transfer_in(self, client: PhxClient) -> None:
        """post_warehouse_transfer_in should POST with correct structure."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"success": True}

            result = await client.post_warehouse_transfer_in(
                stock_code="TEST001",
                warehouse="WH2",
                quantity=15.0,
                notation="Transfer in",
            )

            call_args = mock_request.call_args
            assert "/api/InvMovements/post-warehouse-transfer-in" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_call_business_object_endpoint(self, client: PhxClient) -> None:
        """call_business_object should use correct endpoint path."""
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": "test"}

            result = await client.call_business_object(
                bo_method="Query",
                business_object="INVQRY",
                xml_in="<Query/>",
            )

            call_args = mock_request.call_args
            # Verify the correct endpoint is used (fixed from /api/GenericBo/call)
            assert "/api/BusinessObject/call" in call_args.args[1]
