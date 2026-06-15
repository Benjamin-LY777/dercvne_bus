"""DALI feedback decoder for Dercvne Bus integration."""

import logging
import re

from ..const import (
    FEEDBACK_ON,
    FEEDBACK_OFF,
    FEEDBACK_ADJUST,
    FEEDBACK_QUERY,
)

_LOGGER = logging.getLogger(__name__)


class DALIFeedbackDecoder:
    """Decode feedback from DALI devices."""
    
    @staticmethod
    def parse_feedback(feedback: str) -> dict:
        """Parse feedback string and return structured data.
        
        Args:
            feedback: Feedback string like "*V;@1*S,0,0,1A;"
        
        Returns:
            dict with keys: type, group, address, status, raw
        """
        if not feedback:
            return None
        
        result = {
            "raw": feedback,
            "type": None,
            "group": None,
            "address": None,
            "status": None
        }
        
        # Remove @1 prefix if present
        clean_feedback = re.sub(r'@\d+', '', feedback)
        
        # Check feedback type
        if FEEDBACK_ON in clean_feedback:
            result["type"] = "on"
            result["status"] = "on"
        elif FEEDBACK_OFF in clean_feedback:
            result["type"] = "off"
            result["status"] = "off"
        elif FEEDBACK_ADJUST in clean_feedback:
            result["type"] = "adjust"
        elif FEEDBACK_QUERY in clean_feedback:
            result["type"] = "query"
        
        # Extract group and address
        # Format: *S,0,0,1A; or *C,0,0,1A;
        match = re.search(r'\*[A-Z],(\d),([0-9A-F]),([0-9A-F]{2});', clean_feedback)
        if match:
            result["group"] = match.group(2)
            result["address"] = match.group(3)
        
        _LOGGER.debug(f"Parsed feedback: {result}")
        return result
    
    @staticmethod
    def is_device_on(feedback: str) -> bool:
        """Check if device is on based on feedback."""
        if not feedback:
            return False
        
        clean_feedback = re.sub(r'@\d+', '', feedback)
        return FEEDBACK_ON in clean_feedback
    
    @staticmethod
    def is_device_off(feedback: str) -> bool:
        """Check if device is off based on feedback."""
        if not feedback:
            return False
        
        clean_feedback = re.sub(r'@\d+', '', feedback)
        return FEEDBACK_OFF in clean_feedback
