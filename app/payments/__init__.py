from flask import Blueprint

# Create the payments blueprint (for future integration)
bp = Blueprint('payments', __name__)

# Import routes at the end to avoid circular imports
from app.payments import routes
