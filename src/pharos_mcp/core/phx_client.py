"""
PhX API client for Pharos MCP.

Provides async HTTP client for PhX REST API (SYSPRO WCF wrapper)
with retry logic, rate limit awareness, and SYSPRO error parsing.
"""

import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PhxError(Exception):
    """Base exception for PhX API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        syspro_errors: list[dict[str, str]] | None = None,
        raw_response: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.syspro_errors = syspro_errors or []
        self.raw_response = raw_response


class PhxConnectionError(PhxError):
    """Connection or network error."""

    pass


class PhxRateLimitError(PhxError):
    """Rate limit exceeded (429)."""

    pass


class PhxValidationError(PhxError):
    """SYSPRO validation error in request."""

    pass


class PhxClient:
    """Async HTTP client for PhX REST API.

    Handles:
    - DirectAuth credentials (in request body)
    - Retry with exponential backoff
    - Rate limit awareness (100 req/min)
    - SYSPRO error parsing from responses
    """

    def __init__(
        self,
        base_url: str | None = None,
        operator: str | None = None,
        operator_password: str | None = None,
        company_id: str | None = None,
        company_password: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
    ):
        """Initialize PhX client.

        Args:
            base_url: PhX API base URL (defaults to PHX_URL env var)
            operator: SYSPRO operator (defaults to PHX_OPERATOR env var)
            operator_password: Operator password (defaults to PHX_OPERATOR_PASSWORD env var)
            company_id: SYSPRO company ID (defaults to PHX_COMPANY_ID env var)
            company_password: Company password (defaults to PHX_COMPANY_PASSWORD env var)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts
            retry_delay: Initial delay between retries
            retry_backoff: Exponential backoff multiplier
        """
        self.base_url = (base_url or os.getenv("PHX_URL", "")).rstrip("/")
        self.operator = operator or os.getenv("PHX_OPERATOR", "")
        self.operator_password = operator_password or os.getenv("PHX_OPERATOR_PASSWORD", "")
        self.company_id = company_id or os.getenv("PHX_COMPANY_ID", "")
        self.company_password = company_password or os.getenv("PHX_COMPANY_PASSWORD", "")

        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff

        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return bool(self.base_url and self.operator and self.company_id)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _add_auth(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add DirectAuth credentials to request body.

        Args:
            data: Request data dictionary

        Returns:
            Data with auth credentials added
        """
        auth_fields = {
            "operator": self.operator,
            "operatorPassword": self.operator_password,
            "companyId": self.company_id,
            "companyPassword": self.company_password,
        }
        return {**auth_fields, **data}

    @staticmethod
    def extract_syspro_errors(response_data: dict[str, Any] | str) -> list[dict[str, str]]:
        """Extract SYSPRO errors from API response.

        Handles various error formats from PhX API responses.

        Args:
            response_data: Response data (dict or string)

        Returns:
            List of error dictionaries with 'field', 'value', 'message' keys
        """
        errors: list[dict[str, str]] = []

        if isinstance(response_data, str):
            # Try to parse error messages from string
            # Pattern: "Error: <message>" or SYSPRO error codes
            error_patterns = [
                r"Error[:\s]+(.+?)(?:\n|$)",
                r"ErrorMessage[:\s]+(.+?)(?:\n|$)",
                r"SYSPRO Error[:\s]+(.+?)(?:\n|$)",
            ]
            for pattern in error_patterns:
                matches = re.findall(pattern, response_data, re.IGNORECASE)
                for match in matches:
                    errors.append({"field": "", "value": "", "message": match.strip()})
            return errors

        if not isinstance(response_data, dict):
            return errors

        # Check for explicit error fields
        if "errors" in response_data:
            err_list = response_data["errors"]
            if isinstance(err_list, list):
                for err in err_list:
                    if isinstance(err, dict):
                        errors.append({
                            "field": str(err.get("field", err.get("Field", ""))),
                            "value": str(err.get("value", err.get("Value", ""))),
                            "message": str(
                                err.get("message", err.get("errorMessage", err.get("ErrorMessage", "")))
                            ),
                        })
                    elif isinstance(err, str):
                        errors.append({"field": "", "value": "", "message": err})

        # Check for validation errors
        if "validationErrors" in response_data or "ValidationErrors" in response_data:
            val_errors = response_data.get("validationErrors", response_data.get("ValidationErrors", []))
            if isinstance(val_errors, list):
                for err in val_errors:
                    if isinstance(err, dict):
                        errors.append({
                            "field": str(err.get("Field", err.get("field", ""))),
                            "value": str(err.get("Value", err.get("value", ""))),
                            "message": str(err.get("ErrorMessage", err.get("errorMessage", err.get("message", "")))),
                        })

        # Check for single error message
        if "message" in response_data and response_data.get("success") is False:
            msg = response_data["message"]
            if msg and not errors:  # Don't duplicate if we already have errors
                errors.append({"field": "", "value": "", "message": str(msg)})

        # Check for SYSPRO-specific error structure
        if "errorType" in response_data or "ErrorType" in response_data:
            error_type = response_data.get("errorType", response_data.get("ErrorType", ""))
            error_details = response_data.get("errorDetails", response_data.get("ErrorDetails", ""))
            if error_details and not any(e["message"] == error_details for e in errors):
                errors.append({
                    "field": error_type,
                    "value": "",
                    "message": str(error_details),
                })

        return errors

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        add_auth: bool = True,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            data: Request body data
            add_auth: Whether to add auth credentials

        Returns:
            Response data as dictionary

        Raises:
            PhxConnectionError: Network/connection error
            PhxRateLimitError: Rate limit exceeded
            PhxValidationError: SYSPRO validation error
            PhxError: Other API error
        """
        client = await self._get_client()

        if data is None:
            data = {}
        if add_auth:
            data = self._add_auth(data)

        last_error: Exception | None = None
        delay = self.retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                if method.upper() == "GET":
                    response = await client.get(endpoint)
                else:
                    response = await client.post(endpoint, json=data)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    raise PhxRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after} seconds.",
                        status_code=429,
                    )

                # Parse response
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"raw": response.text}

                # Check for errors in response
                if response.status_code >= 400:
                    errors = self.extract_syspro_errors(response_data)

                    if response.status_code == 400:
                        error_msg = errors[0]["message"] if errors else "Validation error"
                        raise PhxValidationError(
                            error_msg,
                            status_code=400,
                            syspro_errors=errors,
                            raw_response=response.text,
                        )

                    error_msg = errors[0]["message"] if errors else f"HTTP {response.status_code}"
                    raise PhxError(
                        error_msg,
                        status_code=response.status_code,
                        syspro_errors=errors,
                        raw_response=response.text,
                    )

                # Check for SYSPRO errors in successful response
                if isinstance(response_data, dict):
                    if response_data.get("success") is False or response_data.get("Success") is False:
                        errors = self.extract_syspro_errors(response_data)
                        error_msg = errors[0]["message"] if errors else "Operation failed"
                        raise PhxValidationError(
                            error_msg,
                            status_code=response.status_code,
                            syspro_errors=errors,
                            raw_response=response.text,
                        )

                return response_data  # type: ignore[return-value]

            except (PhxRateLimitError, PhxValidationError):
                # Don't retry rate limits or validation errors
                raise

            except httpx.TimeoutException as e:
                last_error = PhxConnectionError(f"Request timeout: {e}")
                logger.warning(f"PhX request timeout (attempt {attempt + 1}/{self.max_retries + 1})")

            except httpx.ConnectError as e:
                last_error = PhxConnectionError(f"Connection error: {e}")
                logger.warning(f"PhX connection error (attempt {attempt + 1}/{self.max_retries + 1}): {e}")

            except PhxError:
                raise

            except Exception as e:
                last_error = PhxError(f"Unexpected error: {e}")
                logger.warning(f"PhX unexpected error (attempt {attempt + 1}/{self.max_retries + 1}): {e}")

            # Wait before retry
            if attempt < self.max_retries:
                import asyncio
                await asyncio.sleep(delay)
                delay *= self.retry_backoff

        # All retries exhausted
        if last_error:
            raise last_error
        raise PhxConnectionError("Request failed after all retries")

    # === Query Methods (read-only) ===

    async def test_connection(self) -> dict[str, Any]:
        """Test connection to PhX API.

        Returns:
            Health check response
        """
        return await self._request("GET", "/health", add_auth=False)

    async def query_inventory(self, stock_code: str) -> dict[str, Any]:
        """Query inventory for a stock code.

        Args:
            stock_code: SYSPRO stock code

        Returns:
            Inventory data
        """
        return await self._request("POST", "/api/QueryBo/inventory", {"stockCode": stock_code})

    async def query_wip_job(
        self,
        job: str,
        include_operations: bool = True,
        include_materials: bool = True,
    ) -> dict[str, Any]:
        """Query WIP job details.

        Args:
            job: Job number
            include_operations: Include operation details
            include_materials: Include material details

        Returns:
            Job data
        """
        data = {
            "job": job,
            "includeOperationAllocations": "Y" if include_operations else "N",
            "includeMaterialAllocations": "Y" if include_materials else "N",
            "includeOperationTransactions": "Y" if include_operations else "N",
            "includeMaterialTransactions": "Y" if include_materials else "N",
        }
        return await self._request("POST", "/api/QueryBo/wip-job", data)

    async def query_wip_tracking(self, job: str) -> dict[str, Any]:
        """Query WIP job tracking/variance information.

        Args:
            job: Job number

        Returns:
            Tracking/variance data
        """
        return await self._request("POST", "/api/QueryBo/wip-tracking", {"job": job})

    async def query_requisition(
        self,
        user: str,
        user_password: str = "",
        requisition_number: str = "",
        include_approved: str = "Y",
    ) -> dict[str, Any]:
        """Query requisitions for a user.

        Args:
            user: Requisition user
            user_password: User password (if required)
            requisition_number: Specific requisition number (optional)
            include_approved: Include approved requisitions (Y/N)

        Returns:
            Requisition data
        """
        data = {
            "requisitionUser": user,
            "userPassword": user_password,
            "requisitionNumber": requisition_number,
            "includeApproved": include_approved,
        }
        return await self._request("POST", "/api/QueryBo/requisition", data)

    # === Transaction Methods (write operations) ===

    async def post_labour(
        self,
        job: str,
        operation: str,
        work_centre: str,
        employee: str = "",
        run_time_hours: float = 0.0,
        qty_complete: float = 0.0,
        oper_completed: str = "N",
        wc_rate_ind: str = "S",
        reference: str = "",
    ) -> dict[str, Any]:
        """Post labour to a job operation.

        Args:
            job: Job number
            operation: Operation number
            work_centre: Work centre code
            employee: Employee code (optional)
            run_time_hours: Run time in hours
            qty_complete: Quantity completed
            oper_completed: Operation completed (Y/N)
            wc_rate_ind: Work centre rate indicator (S=Standard)
            reference: Transaction reference

        Returns:
            Transaction result
        """
        data = {
            "job": job,
            "lOperation": operation,
            "lWorkCentre": work_centre,
            "lEmployee": employee,
            "lRunTimeHours": str(run_time_hours),
            "lQtyComplete": str(qty_complete),
            "operCompleted": oper_completed,
            "lWcRateInd": wc_rate_ind,
            "reference": reference,
        }
        return await self._request("POST", "/api/WipTransaction/post-labour", data)

    async def post_job_receipt(
        self,
        job: str,
        qty_to_manufacture: float,
        receipt_qty: float,
        warehouse: str,
        unit_cost: float | None = None,
        reference: str = "",
    ) -> dict[str, Any]:
        """Post job receipt (complete job).

        Args:
            job: Job number
            qty_to_manufacture: Quantity manufactured
            receipt_qty: Receipt quantity
            warehouse: Receipt warehouse
            unit_cost: Unit cost (optional, uses job cost if not specified)
            reference: Transaction reference

        Returns:
            Transaction result
        """
        data = {
            "job": job,
            "qtyToManufacture": str(qty_to_manufacture),
            "receiptQty": str(receipt_qty),
            "warehouse": warehouse,
            "reference": reference,
        }
        if unit_cost is not None:
            data["unitCost"] = str(unit_cost)
        return await self._request("POST", "/api/WipTransaction/post-job-receipt", data)

    async def post_material(
        self,
        job: str,
        stock_code: str,
        warehouse: str,
        qty_issued: float,
        bin_location: str,
        alloc_completed: str = "N",
        reference: str = "",
    ) -> dict[str, Any]:
        """Post material issue to a job.

        Args:
            job: Job number
            stock_code: Stock code to issue
            warehouse: Source warehouse
            qty_issued: Quantity to issue
            bin_location: Source bin location
            alloc_completed: Allocation completed (Y/N)
            reference: Transaction reference

        Returns:
            Transaction result
        """
        data = {
            "items": [{
                "job": job,
                "stockCode": stock_code,
                "warehouse": warehouse,
                "qtyIssued": str(qty_issued),
                "allocCompleted": alloc_completed,
                "bins": [{
                    "binLocation": bin_location,
                    "binQuantity": str(qty_issued),
                }],
            }],
            "reference": reference,
        }
        return await self._request("POST", "/api/WipTransaction/post-material", data)

    async def approve_requisition(
        self,
        user: str,
        requisition_number: str,
        user_password: str = "",
        requisition_line: str = "",
        e_signature: str = "",
    ) -> dict[str, Any]:
        """Approve a requisition.

        Args:
            user: Approving user
            requisition_number: Requisition to approve
            user_password: User password (if required)
            requisition_line: Specific line to approve (optional, approves all if empty)
            e_signature: Electronic signature (if required)

        Returns:
            Approval result
        """
        data = {
            "user": user,
            "userPassword": user_password,
            "requisitionNumber": requisition_number,
            "requisitionLine": requisition_line,
            "eSignature": e_signature,
        }
        return await self._request("POST", "/api/RequisitionBo/approve", data)

    async def call_business_object(
        self,
        bo_method: str,
        business_object: str,
        xml_in: str,
        xml_parameters: str = "",
    ) -> dict[str, Any]:
        """Call a generic SYSPRO business object.

        This is the gateway for any SYSPRO BO not covered by specific methods.

        Args:
            bo_method: BO method (Query, Post, Build, etc.)
            business_object: Business object name (e.g., INVQRY, WIPTLP)
            xml_in: Input XML for the BO
            xml_parameters: Parameters XML (optional)

        Returns:
            Business object response
        """
        data = {
            "boMethod": bo_method,
            "businessObject": business_object,
            "xmlIn": xml_in,
            "xmlParameters": xml_parameters,
        }
        return await self._request("POST", "/api/BusinessObject/call", data)

    # === Inventory Movement Methods ===

    async def post_immediate_warehouse_transfer(
        self,
        stock_code: str,
        from_warehouse: str,
        to_warehouse: str,
        quantity: float,
        notation: str,
        from_bin: str = "",
        to_bin: str = "",
        reference: str = "",
        unit_of_measure: str = "",
    ) -> dict[str, Any]:
        """Immediate warehouse transfer (single transaction).

        Args:
            stock_code: SYSPRO stock code
            from_warehouse: Source warehouse code
            to_warehouse: Destination warehouse code
            quantity: Quantity to transfer
            notation: Required transaction notation/reason
            from_bin: Source bin location (optional)
            to_bin: Destination bin location (optional)
            reference: Transaction reference (optional)
            unit_of_measure: Unit of measure (optional)

        Returns:
            Transaction result with journal information
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "fromWarehouse": from_warehouse,
            "toWarehouse": to_warehouse,
            "quantity": str(quantity),
            "notation": notation,
        }
        if from_bin:
            item["fromBin"] = from_bin
        if to_bin:
            item["toBin"] = to_bin
        if reference:
            item["reference"] = reference
        if unit_of_measure:
            item["unitOfMeasure"] = unit_of_measure
        return await self._request(
            "POST", "/api/InvMovements/post-immediate-warehouse-transfer", {"items": [item]}
        )

    async def post_bin_transfer(
        self,
        stock_code: str,
        warehouse: str,
        from_bin: str,
        to_bin: str,
        quantity: float,
        notation: str,
        reference: str = "",
    ) -> dict[str, Any]:
        """Transfer stock between bins in the same warehouse.

        Args:
            stock_code: SYSPRO stock code
            warehouse: Warehouse code
            from_bin: Source bin location
            to_bin: Destination bin location
            quantity: Quantity to transfer
            notation: Required transaction notation/reason
            reference: Transaction reference (optional)

        Returns:
            Transaction result with journal information
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "warehouse": warehouse,
            "fromBin": from_bin,
            "toBin": to_bin,
            "quantity": str(quantity),
            "notation": notation,
        }
        if reference:
            item["reference"] = reference
        return await self._request(
            "POST", "/api/InvMovements/post-bin-transfer", {"items": [item]}
        )

    async def post_inventory_adjustment(
        self,
        stock_code: str,
        warehouse: str,
        quantity: float,
        notation: str,
        bin_location: str = "",
        reference: str = "",
        unit_cost: float | None = None,
    ) -> dict[str, Any]:
        """Adjust inventory quantity (positive or negative).

        Args:
            stock_code: SYSPRO stock code
            warehouse: Warehouse code
            quantity: Adjustment quantity (positive to add, negative to remove)
            notation: Required transaction notation/reason
            bin_location: Bin location (optional)
            reference: Transaction reference (optional)
            unit_cost: Unit cost override (optional)

        Returns:
            Transaction result with journal information
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "warehouse": warehouse,
            "quantity": str(quantity),
            "notation": notation,
        }
        if bin_location:
            item["bin"] = bin_location
        if reference:
            item["reference"] = reference
        if unit_cost is not None:
            item["unitCost"] = str(unit_cost)
        return await self._request(
            "POST", "/api/InvMovements/post-inventory-adjustment", {"items": [item]}
        )

    async def post_expense_issue(
        self,
        stock_code: str,
        warehouse: str,
        quantity: float,
        notation: str,
        ledger_code: str,
        bin_location: str = "",
        reference: str = "",
    ) -> dict[str, Any]:
        """Issue stock as an expense.

        Args:
            stock_code: SYSPRO stock code
            warehouse: Source warehouse code
            quantity: Quantity to issue
            notation: Required transaction notation/reason
            ledger_code: GL ledger code to expense to
            bin_location: Source bin location (optional)
            reference: Transaction reference (optional)

        Returns:
            Transaction result with journal information
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "warehouse": warehouse,
            "quantity": str(quantity),
            "notation": notation,
            "ledgerCode": ledger_code,
        }
        if bin_location:
            item["bin"] = bin_location
        if reference:
            item["reference"] = reference
        return await self._request(
            "POST", "/api/InvMovements/post-expense-issue", {"items": [item]}
        )

    async def post_git_transfer_out(
        self,
        stock_code: str,
        from_warehouse: str,
        to_warehouse: str,
        quantity: float,
        notation: str,
        from_bin: str = "",
        reference: str = "",
    ) -> dict[str, Any]:
        """Initiate goods-in-transit transfer out.

        First step of a two-step GIT transfer. Creates GIT record.

        Args:
            stock_code: SYSPRO stock code
            from_warehouse: Source warehouse code
            to_warehouse: Destination warehouse code
            quantity: Quantity to transfer
            notation: Required transaction notation/reason
            from_bin: Source bin location (optional)
            reference: Transaction reference (optional)

        Returns:
            Transaction result with GIT reference
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "fromWarehouse": from_warehouse,
            "toWarehouse": to_warehouse,
            "quantity": str(quantity),
            "notation": notation,
        }
        if from_bin:
            item["fromBin"] = from_bin
        if reference:
            item["reference"] = reference
        return await self._request(
            "POST", "/api/InvMovements/post-git-warehouse-transfer-out", {"items": [item]}
        )

    async def post_git_transfer_in(
        self,
        stock_code: str,
        warehouse: str,
        quantity: float,
        notation: str,
        bin_location: str = "",
        reference: str = "",
    ) -> dict[str, Any]:
        """Receive goods-in-transit transfer.

        Second step of a two-step GIT transfer. Receives GIT inventory.

        Args:
            stock_code: SYSPRO stock code
            warehouse: Receiving warehouse code
            quantity: Quantity to receive
            notation: Required transaction notation/reason
            bin_location: Destination bin location (optional)
            reference: Transaction reference (optional)

        Returns:
            Transaction result with journal information
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "warehouse": warehouse,
            "quantity": str(quantity),
            "notation": notation,
        }
        if bin_location:
            item["bin"] = bin_location
        if reference:
            item["reference"] = reference
        return await self._request(
            "POST", "/api/InvMovements/post-git-warehouse-transfer-in", {"items": [item]}
        )

    async def post_warehouse_transfer_out(
        self,
        stock_code: str,
        from_warehouse: str,
        to_warehouse: str,
        quantity: float,
        notation: str,
        from_bin: str = "",
        reference: str = "",
    ) -> dict[str, Any]:
        """Begin non-immediate warehouse transfer (creates GIT record).

        First step of a two-step warehouse transfer.

        Args:
            stock_code: SYSPRO stock code
            from_warehouse: Source warehouse code
            to_warehouse: Destination warehouse code
            quantity: Quantity to transfer
            notation: Required transaction notation/reason
            from_bin: Source bin location (optional)
            reference: Transaction reference (optional)

        Returns:
            Transaction result with transfer reference
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "fromWarehouse": from_warehouse,
            "toWarehouse": to_warehouse,
            "quantity": str(quantity),
            "notation": notation,
        }
        if from_bin:
            item["fromBin"] = from_bin
        if reference:
            item["reference"] = reference
        return await self._request(
            "POST", "/api/InvMovements/post-warehouse-transfer-out", {"items": [item]}
        )

    async def post_warehouse_transfer_in(
        self,
        stock_code: str,
        warehouse: str,
        quantity: float,
        notation: str,
        bin_location: str = "",
        reference: str = "",
    ) -> dict[str, Any]:
        """Complete non-immediate warehouse transfer.

        Second step of a two-step warehouse transfer.

        Args:
            stock_code: SYSPRO stock code
            warehouse: Receiving warehouse code
            quantity: Quantity to receive
            notation: Required transaction notation/reason
            bin_location: Destination bin location (optional)
            reference: Transaction reference (optional)

        Returns:
            Transaction result with journal information
        """
        item: dict[str, Any] = {
            "stockCode": stock_code,
            "warehouse": warehouse,
            "quantity": str(quantity),
            "notation": notation,
        }
        if bin_location:
            item["bin"] = bin_location
        if reference:
            item["reference"] = reference
        return await self._request(
            "POST", "/api/InvMovements/post-warehouse-transfer-in", {"items": [item]}
        )


# Global client instance
_phx_client: PhxClient | None = None


def get_phx_client() -> PhxClient:
    """Get the global PhX client instance.

    Returns:
        The PhxClient singleton instance.
    """
    global _phx_client
    if _phx_client is None:
        _phx_client = PhxClient()
    return _phx_client


def reset_phx_client() -> None:
    """Reset the global PhX client instance.

    Useful for testing or reconfiguration.
    """
    global _phx_client
    _phx_client = None
