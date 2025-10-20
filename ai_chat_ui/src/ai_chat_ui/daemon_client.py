"""
HTTP client for communicating with ai-cli-bridge daemon V2.0.0
"""

import requests
from typing import Dict, Any, Optional, Tuple


class DaemonClient:
    """Client for ai-cli-bridge daemon API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 2.0):
        """
        Initialize daemon client.
        
        Args:
            base_url: Daemon API base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
    
    def is_running(self) -> bool:
        """
        Check if daemon is running and responsive.
        
        Returns:
            True if daemon responds to health check, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/",
                timeout=self.timeout
            )
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False
        except Exception:
            return False
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get daemon status including all AI instances.
        
        Returns:
            Status dictionary with daemon info and AI states, or None on error
        """
        try:
            response = requests.get(
                f"{self.base_url}/status",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting daemon status: {e}")
            return None
    
    def get_ai_status(self, ai_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status for a specific AI.
        
        Args:
            ai_name: AI identifier (claude, chatgpt, gemini)
            
        Returns:
            AI status dictionary or None on error
        """
        status = self.get_status()
        if status and "ais" in status:
            return status["ais"].get(ai_name)
        return None
    
    def send_prompt(
        self,
        ai_name: str,
        prompt: str,
        wait_for_response: bool = True,
        timeout_s: int = 120,
        debug: bool = False
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Send a prompt to an AI instance.
        
        Args:
            ai_name: AI identifier (claude, chatgpt, gemini)
            prompt: Message to send
            wait_for_response: Wait for AI response
            timeout_s: Response timeout in seconds
            debug: Enable debug output
            
        Returns:
            Tuple of (success, snippet, markdown, metadata)
        """
        try:
            payload = {
                "target": ai_name,
                "prompt": prompt,
                "wait_for_response": wait_for_response,
                "timeout_s": timeout_s,
                "debug": debug
            }
            
            # Use longer timeout for send (AI response can be slow)
            response = requests.post(
                f"{self.base_url}/send",
                json=payload,
                timeout=timeout_s + 10
            )
            response.raise_for_status()
            
            data = response.json()
            return (
                data.get("success", False),
                data.get("snippet"),
                data.get("markdown"),
                data.get("metadata", {})
            )
            
        except requests.Timeout:
            return False, None, None, {"error": "Request timeout"}
        except requests.ConnectionError:
            return False, None, None, {"error": "Cannot connect to daemon"}
        except requests.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_detail = e.response.json().get("detail", error_msg)
            except Exception:
                error_detail = error_msg
            return False, None, None, {"error": error_detail}
        except Exception as e:
            return False, None, None, {"error": str(e)}
    
    def new_session(self, ai_name: str) -> bool:
        """
        Start a new chat session (resets turn count, tokens, etc.).
        
        Args:
            ai_name: AI identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.post(
                f"{self.base_url}/session/new/{ai_name}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json().get("success", False)
        except Exception as e:
            print(f"Error starting new session: {e}")
            return False
