"""
Tempo MRP module descriptions.

Maps Tempo table name patterns to their functional areas.
Unlike SYSPRO, Tempo uses full table names rather than prefixes.
"""

TEMPO_MODULES = {
    # Core MRP Tables
    "Items": "Item Master",
    "Inventory": "Inventory Levels",
    "Demands": "Demand Management",
    "Supply": "Supply Management",
    "Suggestions": "MRP Suggestions",
    "Pegging": "Demand/Supply Pegging",
    "MRPConfiguration": "MRP Settings",
    "Runs": "MRP Run History",
    "ScheduledMRPRuns": "Scheduled MRP Runs",
    "ScheduledMRPRunHistory": "MRP Run History",
    "ActionMessages": "MRP Action Messages",

    # Forecasting
    "ForecastResults": "Forecast Results",
    "ForecastRuns": "Forecast Run History",
    "ForecastAccuracy": "Forecast Accuracy Metrics",
    "ForecastMethodPerformance": "Forecast Method Analysis",
    "ForecastConsumptionTracking": "Forecast Consumption",
    "ItemForecasts": "Item-Level Forecasts",
    "ItemForecastStrategy": "Item Forecast Settings",
    "CategoryForecastStrategy": "Category Forecast Settings",

    # Classification (ABC Analysis)
    "ItemClassification": "Item ABC Classification",
    "ItemClassificationConfig": "Classification Settings",
    "ItemClassificationHistory": "Classification History",
    "ClassificationCalculationRun": "Classification Runs",

    # Buffer Management
    "ItemBufferLevels": "Buffer/Safety Stock Levels",
    "BufferCalculationConfig": "Buffer Calculation Settings",
    "BufferTrustConfiguration": "Buffer Trust Settings",

    # Lead Time
    "LeadTimeCalculationConfig": "Lead Time Settings",
    "LeadTimeDetail": "Lead Time Details",
    "LeadTimeMetrics": "Lead Time Metrics",

    # Jobs/Scheduling
    "JobSchedule": "Job Scheduling",
    "JobConfirmationConfig": "Job Confirmation Settings",
    "ProductionResources": "Production Resources",
    "ResourceAvailability": "Resource Availability",

    # Companies/Multi-tenant
    "Companies": "Company Master",
    "CompanyLicenses": "Company Licensing",

    # User Management
    "Users": "User Management",
    "UserSessions": "User Sessions",
    "UserRoles": "User Role Assignments",
    "UserNotifications": "User Notifications",
    "UserCompanyPermissions": "Company-Level Permissions",
    "UserWarehousePermissions": "Warehouse-Level Permissions",

    # Security/Roles
    "Roles": "Role Definitions",
    "RolePermissions": "Role Permissions",
    "RoleTemplates": "Role Templates",
    "Permissions": "Permission Definitions",
    "PermissionGroups": "Permission Groups",

    # Licensing
    "Licenses": "License Management",
    "LicenseFeatures": "License Features",
    "LicenseUsageMetrics": "License Usage",
    "LicenseAudit": "License Audit Trail",

    # Audit/Tracking
    "AuditLog": "System Audit Log",
    "SuggestionAudit": "Suggestion Audit Trail",
    "UsageTracking": "Feature Usage Tracking",
    "APIUsageMetrics": "API Usage Metrics",
    "ItemUsageAnalysis": "Item Usage Analysis",

    # Communication
    "Comments": "Comments",
    "CommentMentions": "Comment Mentions",

    # Consumption
    "ConsumptionData": "Consumption History",
    "CurrentUsage": "Current Usage Data",
}


def get_tempo_module_for_table(table_name: str) -> str:
    """Get the Tempo module/functional area for a table."""
    return TEMPO_MODULES.get(table_name, "")
