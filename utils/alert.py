"""
Alert module for Vietstock Crawler (Logging only - no email)
Detects captcha/bot detection and logs alerts
"""

import logging
from datetime import datetime
from pathlib import Path

from config import CAPTCHA_KEYWORDS

logger = logging.getLogger(__name__)


class CaptchaDetector:
    """Detects captcha and bot detection pages"""

    @staticmethod
    def detect_captcha(page_content: str, page_title: str = "") -> tuple[bool, str]:
        """
        Detect if page contains captcha or bot detection

        Args:
            page_content: HTML content of the page
            page_title: Page title

        Returns:
            Tuple of (is_detected, reason)
        """
        content_lower = page_content.lower()
        title_lower = page_title.lower()

        for keyword in CAPTCHA_KEYWORDS:
            if keyword.lower() in content_lower or keyword.lower() in title_lower:
                return True, f"Keyword '{keyword}' detected"

        return False, ""

    @staticmethod
    def detect_error_status(status_code: int) -> tuple[bool, str]:
        """
        Detect if status code indicates bot detection

        Args:
            status_code: HTTP status code

        Returns:
            Tuple of (is_detected, reason)
        """
        if status_code == 403:
            return True, "HTTP 403 Forbidden - Possible bot detection"
        elif status_code == 429:
            return True, "HTTP 429 Too Many Requests - Rate limited"
        elif status_code >= 500:
            return True, f"HTTP {status_code} Server Error"

        return False, ""


class AlertManager:
    """Logs alerts (replaces email alerts)"""

    def __init__(self):
        pass

    def log_alert(
        self,
        subject: str,
        body: str,
        screenshot_path: Path | None = None
    ) -> bool:
        """
        Log an alert to file and console

        Args:
            subject: Alert subject
            body: Alert body text
            screenshot_path: Optional path to screenshot

        Returns:
            True if logged successfully
        """
        try:
            logger.warning(f"ALERT: {subject}")
            logger.warning(body)

            if screenshot_path:
                logger.info(f"Screenshot saved to: {screenshot_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to log alert: {e}")
            return False

    async def log_captcha_alert(
        self,
        url: str,
        reason: str,
        screenshot_path: Path | None = None
    ) -> bool:
        """
        Log captcha detection alert

        Args:
            url: The URL where captcha was detected
            reason: Reason for detection
            screenshot_path: Optional path to screenshot

        Returns:
            True if logged successfully
        """
        subject = "CAPTCHA/BOT DETECTION DETECTED"
        body = f"""
Captcha or bot detection was detected while crawling.

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
URL: {url}
Reason: {reason}

The crawler will pause for 5 minutes before retrying.
"""
        return self.log_alert(subject, body, screenshot_path)

    async def log_error_alert(
        self,
        error_message: str,
        context: str = ""
    ) -> bool:
        """
        Log error alert

        Args:
            error_message: The error message
            context: Additional context about the error

        Returns:
            True if logged successfully
        """
        subject = "CRAWLER ERROR DETECTED"
        body = f"""
An error occurred in the Vietstock crawler.

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Error:
{error_message}

Context:
{context}
"""
        return self.log_alert(subject, body)


# Global instances
_detector: CaptchaDetector | None = None
_alert: AlertManager | None = None


def get_detector() -> CaptchaDetector:
    """Get or create the global captcha detector instance"""
    global _detector
    if _detector is None:
        _detector = CaptchaDetector()
    return _detector


def get_alert() -> AlertManager:
    """Get or create the global alert instance"""
    global _alert
    if _alert is None:
        _alert = AlertManager()
    return _alert
