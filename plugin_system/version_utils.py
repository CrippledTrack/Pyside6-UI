"""
Version utilities for plugin compatibility checking.

Supports both simple version strings (e.g., "3.0.0") and range-based
specifications (e.g., ">=3.0.0,<4.0.0").
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_version(version_str: str) -> List[int]:
    """
    Parse a semantic version string into a list of integers.
    
    Args:
        version_str: Version string (e.g., "3.0.0", "2.1.5")
        
    Returns:
        List of integers representing [major, minor, patch]
        Returns [0, 0, 0] if parsing fails
    """
    if not version_str or not isinstance(version_str, str):
        return [0, 0, 0]
    
    # Extract version numbers (handle things like "v3.0.0" or "3.0.0-beta")
    match = re.match(r'^v?(\d+)\.(\d+)(?:\.(\d+))?', version_str.strip())
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else 0
        return [major, minor, patch]
    
    logger.warning(f"Failed to parse version string: {version_str}")
    return [0, 0, 0]


def compare_versions(version1: List[int], version2: List[int]) -> int:
    """
    Compare two version lists.
    
    Args:
        version1: First version as [major, minor, patch]
        version2: Second version as [major, minor, patch]
        
    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2
    """
    for v1, v2 in zip(version1, version2):
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
    return 0


def check_simple_version(gui_version: str, min_version: str) -> bool:
    """
    Check if GUI version meets simple minimum version requirement.
    
    Args:
        gui_version: Current GUI version (e.g., "3.0.0")
        min_version: Minimum required version (e.g., "3.0.0")
        
    Returns:
        True if compatible, False otherwise
    """
    gui_ver = parse_version(gui_version)
    min_ver = parse_version(min_version)
    
    return compare_versions(gui_ver, min_ver) >= 0


def parse_range_requirement(requirement: str) -> List[Tuple[str, str]]:
    """
    Parse a range-based version requirement.
    
    Args:
        requirement: Range specification (e.g., ">=3.0.0,<4.0.0")
        
    Returns:
        List of (operator, version) tuples, e.g., [(">=", "3.0.0"), ("<", "4.0.0")]
    """
    if not requirement:
        return []
    
    # Split by commas and parse each constraint
    constraints = []
    parts = [p.strip() for p in requirement.split(',')]
    
    for part in parts:
        # Match operators: >=, <=, >, <, ==, =
        match = re.match(r'^([><=]+)\s*(.+)$', part)
        if match:
            operator = match.group(1).strip()
            version = match.group(2).strip()
            constraints.append((operator, version))
        else:
            # If no operator, treat as minimum version (>=)
            constraints.append(('>=', part))
    
    return constraints


def check_range_version(gui_version: str, requirement: str) -> bool:
    """
    Check if GUI version meets range-based version requirement.
    
    Args:
        gui_version: Current GUI version (e.g., "3.0.0")
        requirement: Range specification (e.g., ">=3.0.0,<4.0.0")
        
    Returns:
        True if compatible, False otherwise
    """
    constraints = parse_range_requirement(requirement)
    if not constraints:
        return True
    
    gui_ver = parse_version(gui_version)
    
    for operator, req_version in constraints:
        req_ver = parse_version(req_version)
        comparison = compare_versions(gui_ver, req_ver)
        
        if operator == '>=':
            if comparison < 0:
                return False
        elif operator == '>':
            if comparison <= 0:
                return False
        elif operator == '<=':
            if comparison > 0:
                return False
        elif operator == '<':
            if comparison >= 0:
                return False
        elif operator in ('==', '='):
            if comparison != 0:
                return False
        else:
            logger.warning(f"Unknown version operator: {operator}")
            return False
    
    return True


def check_version_compatibility(gui_version: str, 
                                min_gui_version: Optional[str] = None,
                                required_gui_version: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if the current GUI version is compatible with plugin requirements.
    
    Args:
        gui_version: Current GUI version (e.g., "3.0.0")
        min_gui_version: Simple minimum version requirement (e.g., "3.0.0")
        required_gui_version: Advanced range requirement (e.g., ">=3.0.0,<4.0.0")
        
    Returns:
        Tuple of (is_compatible, error_message)
        error_message is None if compatible, or a string describing the issue if not
    """
    # If no requirements specified, assume compatible
    if not min_gui_version and not required_gui_version:
        return True, None
    
    # required_gui_version takes precedence if both are specified
    if required_gui_version:
        try:
            if not check_range_version(gui_version, required_gui_version):
                return False, f"GUI version {gui_version} does not meet requirement: {required_gui_version}"
        except Exception as e:
            logger.error(f"Error checking version requirement '{required_gui_version}': {e}")
            return False, f"Invalid version requirement format: {required_gui_version}"
    
    # Check simple minimum version if specified
    elif min_gui_version:
        try:
            if not check_simple_version(gui_version, min_gui_version):
                return False, f"GUI version {gui_version} is below minimum required: {min_gui_version}"
        except Exception as e:
            logger.error(f"Error checking minimum version '{min_gui_version}': {e}")
            return False, f"Invalid minimum version format: {min_gui_version}"
    
    return True, None


def get_gui_version() -> str:
    """
    Get the current GUI API version.
    
    This function uses GUI/app/constants.py as the single source of truth.
    Returns:
        Current GUI version string (e.g., "3.0.0")
    """
    try:
        from ..app.constants import GUI_API_VERSION
        return GUI_API_VERSION
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not import GUI version constant, assuming 4.0.0: {e}")
        return "4.0.0"


__all__ = [
    'parse_version',
    'compare_versions',
    'check_simple_version',
    'parse_range_requirement',
    'check_range_version',
    'check_version_compatibility',
    'get_gui_version',
]