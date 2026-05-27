from jwt import InvalidTokenError



class AAsuError(Exception):
    """Base class for all AAsu exceptions."""
    pass



class JwtDenied(InvalidTokenError):
    """Raised only when either verify_token or verify_data fails."""
    pass
