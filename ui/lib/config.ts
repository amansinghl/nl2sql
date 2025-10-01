// Frontend configuration for flexible scoping
export const API_CONFIG = {
  // Scoping field configuration
  scopingField: process.env.NEXT_PUBLIC_SCOPING_FIELD || 'scoping_value',
  scopingFieldLabel: process.env.NEXT_PUBLIC_SCOPING_FIELD_LABEL || 'Scoping Value',
  scopingFieldPlaceholder: process.env.NEXT_PUBLIC_SCOPING_FIELD_PLACEHOLDER || 'company123',
  requireScoping: process.env.NEXT_PUBLIC_REQUIRE_SCOPING !== 'false',
  
  // Legacy support
  legacyEntityIdField: process.env.NEXT_PUBLIC_LEGACY_ENTITY_ID === 'true',
  entityIdFieldLabel: process.env.NEXT_PUBLIC_ENTITY_ID_LABEL || 'Entity ID',
  entityIdFieldPlaceholder: process.env.NEXT_PUBLIC_ENTITY_ID_PLACEHOLDER || 'company123',
  
  // API endpoints
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
  
  // UI configuration
  showScopingField: process.env.NEXT_PUBLIC_SHOW_SCOPING_FIELD !== 'false',
  showLegacyEntityId: process.env.NEXT_PUBLIC_SHOW_LEGACY_ENTITY_ID === 'true',
}

// Helper function to get the appropriate scoping field name
export function getScopingFieldName(): string {
  return API_CONFIG.legacyEntityIdField ? 'entity_id' : API_CONFIG.scopingField
}

// Helper function to get the appropriate scoping field label
export function getScopingFieldLabel(): string {
  return API_CONFIG.legacyEntityIdField ? API_CONFIG.entityIdFieldLabel : API_CONFIG.scopingFieldLabel
}

// Helper function to get the appropriate scoping field placeholder
export function getScopingFieldPlaceholder(): string {
  return API_CONFIG.legacyEntityIdField ? API_CONFIG.entityIdFieldPlaceholder : API_CONFIG.scopingFieldPlaceholder
}
