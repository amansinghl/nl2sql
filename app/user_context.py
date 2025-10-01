"""
User Context and Permission Management System

This module provides comprehensive user context management, role-based access control,
and permission validation for the NL2SQL system.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from .config import settings
from .loggery import access_logger as _access_logger_singleton, query_logger as _query_logger_singleton
from .error_codes import ErrorCodes, create_validation_error

logger = logging.getLogger(__name__)

class AccessPattern(Enum):
    """Access patterns for different user roles"""
    SINGLE_ENTITY = "single_entity"
    ALL_ENTITIES = "all_entities"
    MULTIPLE_ENTITIES = "multiple_entities"
    WHITELIST_ENTITIES = "whitelist_entities"

@dataclass
class UserContext:
    """Comprehensive user context for access control"""
    role: str
    scoping_value: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.permissions is None:
            self.permissions = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserContext':
        """Create from dictionary"""
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class PermissionManager:
    """Manages user permissions and access control"""
    
    def __init__(self):
        self.security_config = settings.security
        self.roles_config = self.security_config.get_roles_config()
    
    def create_user_context(
        self,
        role: str,
        scoping_value: str = None,
        request_id: str = None,
        additional_permissions: Dict[str, Any] = None
    ) -> UserContext:
        """Create a user context with proper validation"""
        
        # Validate role
        if role is None:
            role = self.security_config.DEFAULT_USER_ROLE
        
        print(f"Validating role: {role}")
        print(f"Available roles: {list(self.security_config.get_roles_config().keys())}")
        if not self.security_config.is_role_allowed(role):
            raise ValueError(f"Invalid role: {role}")
        
        # Get role configuration
        role_config = self.security_config.get_role_config(role)
        
        # Validate entity access based on role
        validated_entity_access = self._validate_entity_access(
            role, scoping_value
        )
        
        # Create permissions based on role
        permissions = self._create_permissions(role, role_config, validated_entity_access)
        
        if additional_permissions:
            permissions.update(additional_permissions)
        
        return UserContext(
            role=role,
            scoping_value=validated_entity_access.get('primary_entity'),
            permissions=permissions,
            request_id=request_id
        )
    
    def _validate_entity_access(
        self,
        role: str,
        scoping_value: str = None
    ) -> Dict[str, Any]:
        """Validate and process entity access based on role"""
        
        role_config = self.security_config.get_role_config(role)
        access_pattern = role_config.get('access_pattern', 'single_entity')
        
        if access_pattern == 'single_entity':
            if not scoping_value:
                raise ValueError(f"Role '{role}' requires a single scoping value")
            return {
                'primary_entity': scoping_value,
                'accessible_entities': [scoping_value],
                'access_pattern': AccessPattern.SINGLE_ENTITY
            }

        elif access_pattern == 'all_entities':
            # Admin role has full access to all entities
            return {
                'primary_entity': scoping_value,
                'accessible_entities': None,  # None means all entities
                'access_pattern': AccessPattern.ALL_ENTITIES
            }
        
        
        else:
            raise ValueError(f"Unknown access pattern: {access_pattern}")
    
    def _create_permissions(self, role: str, role_config: Dict[str, Any], entity_access: Dict[str, Any]) -> Dict[str, Any]:
        """Create permissions based on role and entity access"""
        
        permissions = {
            'can_query': True,
            'can_access_all_entities': entity_access['access_pattern'] == AccessPattern.ALL_ENTITIES,
            'can_scope_to_specific': role_config.get('can_scope_to_specific', False),
            'requires_scoping': role_config.get('requires_scoping', True),
            'bypass_validation': role_config.get('bypass_validation', False),
            'max_entities_per_query': self.security_config.MAX_ENTITIES_PER_QUERY,
            'can_cross_entity_query': self.security_config.ENABLE_CROSS_ENTITY_QUERIES,
            'accessible_entities': entity_access['accessible_entities'],
            'access_pattern': entity_access['access_pattern'].value
        }
        
        return permissions
    
    def validate_query_access(self, user_context: UserContext, query_entities: List[str] = None) -> Dict[str, Any]:
        """Validate if user can access the requested entities"""
        
        if not user_context.permissions.get('can_query', False):
            return {
                'allowed': False,
                'error': 'User does not have query permissions',
                'error_code': ErrorCodes.AUTH_INSUFFICIENT_PERMISSIONS.code
            }
        
        # If user can access all entities, allow any query
        if user_context.permissions.get('can_access_all_entities', False):
            return {'allowed': True, 'scoping_required': False}
        
        # Check specific entity access
        accessible_entities = user_context.permissions.get('accessible_entities')
        if accessible_entities is None:  # All entities allowed
            return {'allowed': True, 'scoping_required': False}
        
        if query_entities:
            # Check if all requested entities are accessible
            inaccessible = set(query_entities) - set(accessible_entities)
            if inaccessible:
                return {
                    'allowed': False,
                    'error': f'Access denied to entities: {list(inaccessible)}',
                    'error_code': ErrorCodes.AUTH_INSUFFICIENT_PERMISSIONS.code
                }
        
        return {
            'allowed': True, 
            'scoping_required': user_context.permissions.get('requires_scoping', True),
            'accessible_entities': accessible_entities
        }
    
    def get_scoping_requirements(self, user_context: UserContext) -> Dict[str, Any]:
        """Get scoping requirements for a user context"""
        
        print(f"Getting scoping requirements for role: {user_context.role}")
        print(f"Permissions: {user_context.permissions}")
        
        if user_context.permissions.get('bypass_validation', False):
            print("Bypassing validation due to bypass_validation=True")
            return {'scoping_required': False, 'scoping_column': None}
        
        if not user_context.permissions.get('requires_scoping', True):
            print("No scoping required due to requires_scoping=False")
            return {'scoping_required': False, 'scoping_column': None}
        
        return {
            'scoping_required': True,
            'scoping_column': self.security_config.SCOPING_COLUMN,
            'scoping_value': user_context.scoping_value,
            'accessible_entities': user_context.permissions.get('accessible_entities')
        }


# Global instances
permission_manager = PermissionManager()
access_logger = _access_logger_singleton
query_logger = _query_logger_singleton
