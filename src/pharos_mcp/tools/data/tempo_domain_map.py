"""
Tempo MRP domain knowledge: maps business concepts to table names.

Tempo is a dedicated MRP (Material Requirements Planning) system that
integrates with SYSPRO. It uses a run-based data model where each MRP
run creates a snapshot of planning data.
"""

TEMPO_DOMAIN_MAP = {
    # Items/Products
    "item": ["Items", "ItemClassification", "ItemBufferLevels"],
    "items": ["Items", "ItemClassification", "ItemBufferLevels"],
    "stock": ["Items", "Inventory"],
    "product": ["Items"],
    "products": ["Items"],
    "stock code": ["Items", "Inventory"],

    # Inventory
    "inventory": ["Inventory"],
    "on hand": ["Inventory"],
    "available": ["Inventory"],
    "warehouse": ["Inventory", "UserWarehousePermissions"],

    # MRP Core
    "mrp": ["MRPConfiguration", "Runs", "ScheduledMRPRuns"],
    "planning": ["MRPConfiguration", "Suggestions", "Demands", "Supply"],
    "run": ["Runs", "ScheduledMRPRuns", "ScheduledMRPRunHistory"],
    "runs": ["Runs", "ScheduledMRPRuns", "ScheduledMRPRunHistory"],

    # Demand
    "demand": ["Demands"],
    "demands": ["Demands"],
    "requirement": ["Demands", "Suggestions"],
    "requirements": ["Demands", "Suggestions"],

    # Supply
    "supply": ["Supply"],
    "order": ["Supply", "Suggestions"],
    "orders": ["Supply", "Suggestions"],

    # Suggestions/Recommendations
    "suggestion": ["Suggestions", "SuggestionAudit"],
    "suggestions": ["Suggestions", "SuggestionAudit"],
    "recommendation": ["Suggestions"],
    "recommendations": ["Suggestions"],
    "planned order": ["Suggestions"],
    "action": ["ActionMessages", "Suggestions"],
    "exception": ["Suggestions"],

    # Pegging
    "pegging": ["Pegging"],
    "peg": ["Pegging"],
    "allocation": ["Pegging", "Demands", "Supply"],

    # Forecasting
    "forecast": ["ForecastResults", "ForecastRuns", "ItemForecasts"],
    "forecasts": ["ForecastResults", "ForecastRuns", "ItemForecasts"],
    "forecasting": ["ForecastResults", "ForecastMethodPerformance"],
    "prediction": ["ForecastResults", "ItemForecasts"],
    "accuracy": ["ForecastAccuracy", "ForecastMethodPerformance"],

    # Classification (ABC)
    "classification": ["ItemClassification", "ItemClassificationHistory"],
    "abc": ["ItemClassification", "ClassificationCalculationRun"],
    "abc analysis": ["ItemClassification", "ItemClassificationConfig"],
    "category": ["ItemClassification", "CategoryForecastStrategy"],

    # Buffer Management
    "buffer": ["ItemBufferLevels", "BufferCalculationConfig"],
    "buffers": ["ItemBufferLevels", "BufferCalculationConfig"],
    "safety stock": ["ItemBufferLevels", "Items", "Inventory"],
    "reorder": ["ItemBufferLevels"],

    # Lead Time
    "lead time": ["LeadTimeDetail", "LeadTimeMetrics", "Items"],
    "leadtime": ["LeadTimeDetail", "LeadTimeMetrics", "Items"],

    # Jobs/Production
    "job": ["JobSchedule", "JobConfirmationConfig"],
    "jobs": ["JobSchedule"],
    "schedule": ["JobSchedule", "ScheduledMRPRuns"],
    "production": ["ProductionResources", "JobSchedule"],
    "resource": ["ProductionResources", "ResourceAvailability"],
    "resources": ["ProductionResources", "ResourceAvailability"],

    # Companies/Organization
    "company": ["Companies", "UserCompanyPermissions"],
    "companies": ["Companies"],
    "organization": ["Companies"],

    # Users/Security
    "user": ["Users", "UserSessions", "UserRoles"],
    "users": ["Users"],
    "role": ["Roles", "RolePermissions", "UserRoles"],
    "roles": ["Roles", "RoleTemplates"],
    "permission": ["Permissions", "RolePermissions", "PermissionGroups"],
    "permissions": ["Permissions", "RolePermissions"],
    "session": ["UserSessions"],

    # Licensing
    "license": ["Licenses", "LicenseFeatures", "LicenseUsageMetrics"],
    "licenses": ["Licenses", "CompanyLicenses"],
    "licensing": ["Licenses", "LicenseAudit"],

    # Audit/Tracking
    "audit": ["AuditLog", "SuggestionAudit", "LicenseAudit"],
    "log": ["AuditLog"],
    "history": ["ItemClassificationHistory", "ScheduledMRPRunHistory"],
    "tracking": ["UsageTracking", "ForecastConsumptionTracking"],
    "usage": ["UsageTracking", "APIUsageMetrics", "ItemUsageAnalysis"],

    # Comments/Communication
    "comment": ["Comments", "CommentMentions"],
    "comments": ["Comments"],
    "notification": ["UserNotifications"],
    "notifications": ["UserNotifications"],
    "message": ["ActionMessages"],
    "messages": ["ActionMessages"],

    # Configuration
    "config": ["MRPConfiguration", "BufferCalculationConfig", "LeadTimeCalculationConfig"],
    "configuration": ["MRPConfiguration", "BufferCalculationConfig"],
    "settings": ["MRPConfiguration", "ItemClassificationConfig"],

    # Consumption
    "consumption": ["ConsumptionData", "ForecastConsumptionTracking"],
}
