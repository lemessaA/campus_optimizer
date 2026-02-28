# src/core/exceptions.py
# this file contains custom exceptions for the campus optimizer system
class CampusOptimizerError(Exception):
    """Base exception for campus optimizer system"""
    pass


class SchedulingError(CampusOptimizerError):
    """Exception raised when scheduling operations fail"""
    pass

class DatabaseError(CampusOptimizerError):
    """Exception raised when database operations fail"""
    pass

class AgentError(CampusOptimizerError):
    """Exception raised when agent operations fail"""
    pass

class ConfigurationError(CampusOptimizerError):
    """Exception raised when configuration is invalid"""
    pass