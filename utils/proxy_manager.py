"""
Proxy Manager module for Vietstock Crawler
Handles proxy rotation and health checks
"""

import asyncio
import random
from pathlib import Path

import aiohttp

from config import PROXY_FILE, USE_PROXY


class ProxyManager:
    """Manages proxy rotation and health checking"""

    def __init__(self, proxy_file: Path = PROXY_FILE):
        self.proxy_file = proxy_file
        self.proxies: list[str] = []
        self.dead_proxies: list[str] = []
        self.current_proxy: str | None = None

    def load_proxies(self) -> None:
        """Load proxies from file"""
        self.proxies = []
        self.dead_proxies = []

        if not self.proxy_file.exists():
            print(f"Proxy file not found: {self.proxy_file}")
            return

        try:
            with open(self.proxy_file, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        # Support formats: IP:PORT or IP:PORT:USER:PASS
                        parts = line.split(':')
                        if len(parts) >= 2:
                            self.proxies.append(line)

            print(f"Loaded {len(self.proxies)} proxies from {self.proxy_file}")
        except Exception as e:
            print(f"Error loading proxies: {e}")

    def get_random_proxy(self) -> str | None:
        """
        Get a random proxy from the healthy list

        Returns:
            Proxy string or None if no proxies available
        """
        if not self.proxies:
            return None

        # Remove dead proxies and get a random one
        available_proxies = [p for p in self.proxies if p not in self.dead_proxies]

        if not available_proxies:
            # All proxies are dead, reset dead list
            self.dead_proxies = []
            available_proxies = self.proxies

        if available_proxies:
            self.current_proxy = random.choice(available_proxies)
            return self.current_proxy

        return None

    def mark_dead(self, proxy: str) -> None:
        """
        Mark a proxy as dead

        Args:
            proxy: The proxy to mark as dead
        """
        if proxy not in self.dead_proxies:
            self.dead_proxies.append(proxy)
            print(f"Marked proxy as dead: {proxy}")

    def get_proxy_dict(self, proxy: str | None = None) -> dict | None:
        """
        Convert proxy string to dictionary format for requests/playwright

        Args:
            proxy: Proxy string (format: IP:PORT or IP:PORT:USER:PASS)

        Returns:
            Dictionary with proxy settings or None
        """
        if not proxy:
            return None

        parts = proxy.split(':')

        if len(parts) == 2:
            # Format: IP:PORT
            return {
                'server': f"http://{parts[0]}:{parts[1]}",
            }
        elif len(parts) == 4:
            # Format: IP:PORT:USER:PASS
            return {
                'server': f"http://{parts[0]}:{parts[1]}",
                'username': parts[2],
                'password': parts[3],
            }

        return None

    async def check_proxy(self, proxy: str, timeout: int = 10) -> bool:
        """
        Check if a proxy is working

        Args:
            proxy: Proxy string to check
            timeout: Timeout in seconds

        Returns:
            True if proxy is working, False otherwise
        """
        proxy_dict = self.get_proxy_dict(proxy)
        if not proxy_dict:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'http://httpbin.org/ip',
                    proxy=proxy_dict['server'],
                    proxy_basic_auth=(
                        (proxy_dict.get('username'), proxy_dict.get('password'))
                        if 'username' in proxy_dict else None
                    ),
                    timeout=timeout
                ) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Proxy check failed for {proxy}: {e}")
            return False

    async def check_all_proxies(self) -> None:
        """Check all proxies and remove dead ones"""
        if not self.proxies:
            return

        print(f"Checking {len(self.proxies)} proxies...")

        tasks = [self.check_proxy(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks)

        for proxy, is_alive in zip(self.proxies, results, strict=False):
            if not is_alive:
                self.mark_dead(proxy)

        alive_count = len(self.proxies) - len(self.dead_proxies)
        print(f"Proxy check complete: {alive_count}/{len(self.proxies)} proxies alive")

    def get_stats(self) -> dict:
        """
        Get proxy statistics

        Returns:
            Dictionary with proxy stats
        """
        alive_count = len(self.proxies) - len(self.dead_proxies)
        return {
            'total': len(self.proxies),
            'alive': alive_count,
            'dead': len(self.dead_proxies),
            'current': self.current_proxy,
        }


# Global proxy manager instance
_proxy_manager: ProxyManager | None = None


def get_proxy_manager() -> ProxyManager:
    """Get or create the global proxy manager instance"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
        if USE_PROXY:
            _proxy_manager.load_proxies()
    return _proxy_manager


def should_use_proxy() -> bool:
    """Check if proxy should be used based on config and availability"""
    if not USE_PROXY:
        return False

    manager = get_proxy_manager()
    return len(manager.proxies) > 0
