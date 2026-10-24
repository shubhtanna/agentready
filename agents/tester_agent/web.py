"""A plain-HTTP 'browser' that sees a website the way most AI shopping agents do.

No JavaScript is executed. Cookies are kept within one session (like an agent
working through a task), robots.txt is honoured, and every request is logged so
the final report can show its evidence.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = (
    "Mozilla/5.0 (compatible; AgentReady-Shopper/1.0; +https://agentready-five-rust.vercel.app) "
    "AI shopping agent test"
)
TIMEOUT = httpx.Timeout(45.0, connect=20.0)  # free-tier hosts can take ~40 s to wake

# Well-known AI agents and crawlers whose access we report on.
AI_AGENTS = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "PerplexityBot", "Google-Extended", "CCBot"]


@dataclass
class Page:
    url: str
    status: int
    text: str
    content_type: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


@dataclass
class Robots:
    found: bool
    parser: RobotFileParser | None = None
    blocked_agents: list[str] = field(default_factory=list)

    def allows(self, url: str) -> bool:
        if not self.parser:
            return True
        # We act as a generic automated agent, so the '*' group applies.
        return self.parser.can_fetch("AgentReady-Shopper", url)


class Browser:
    def __init__(self, base_url: str):
        if not re.match(r"^https?://", base_url):
            base_url = "https://" + base_url
        p = urlparse(base_url)
        self.origin = f"{p.scheme}://{p.netloc}"
        self.start_url = base_url
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        self.robots: Robots | None = None
        self.log: list[str] = []

    async def close(self):
        await self.client.aclose()

    def same_site(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.origin).netloc

    def abs(self, href: str, base: str | None = None) -> str:
        return urljoin(base or self.origin + "/", href)

    async def load_robots(self) -> Robots:
        page = await self.get(self.origin + "/robots.txt", check_robots=False)
        if not page.ok or "html" in page.content_type:
            self.robots = Robots(found=False)
            return self.robots
        rp = RobotFileParser()
        rp.parse(page.text.splitlines())
        blocked = [a for a in AI_AGENTS if not rp.can_fetch(a, self.origin + "/")]
        self.robots = Robots(found=True, parser=rp, blocked_agents=blocked)
        return self.robots

    async def get(self, url: str, check_robots: bool = True) -> Page:
        if check_robots and self.robots and not self.robots.allows(url):
            self.log.append(f"SKIP (robots.txt) GET {url}")
            return Page(url, 999, "")
        try:
            r = await self.client.get(url)
            self.log.append(f"GET {url} -> {r.status_code}")
            return Page(str(r.url), r.status_code, r.text, r.headers.get("content-type", ""))
        except httpx.HTTPError as err:
            self.log.append(f"GET {url} -> error {type(err).__name__}")
            return Page(url, 0, "")

    async def post_form(self, url: str, data: list[tuple[str, str]], multipart: bool = False, referer: str | None = None) -> Page:
        if self.robots and not self.robots.allows(url):
            self.log.append(f"SKIP (robots.txt) POST {url}")
            return Page(url, 999, "")
        headers = {"Referer": referer} if referer else {}
        try:
            if multipart:
                boundary = "----AgentReady" + secrets.token_hex(8)
                crlf = chr(13) + chr(10)
                parts = [f'--{boundary}{crlf}Content-Disposition: form-data; name="{k}"{crlf}{crlf}{v}{crlf}' for k, v in data]
                body = ("".join(parts) + f"--{boundary}--{crlf}").encode()
                headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
                r = await self.client.post(url, content=body, headers=headers)
            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                r = await self.client.post(url, content=urlencode(data).encode(), headers=headers)
            self.log.append(f"POST {url} -> {r.status_code}")
            return Page(str(r.url), r.status_code, r.text, r.headers.get("content-type", ""))
        except httpx.HTTPError as err:
            self.log.append(f"POST {url} -> error {type(err).__name__}")
            return Page(url, 0, "")

    async def get_many(self, urls: list[str], limit: int = 6) -> list[Page]:
        sem = asyncio.Semaphore(limit)

        async def one(u):
            async with sem:
                return await self.get(u)

        return await asyncio.gather(*(one(u) for u in urls))


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


async def browser_status(url: str) -> int:
    """Diagnosis only: the HTTP status a normal browser gets. Used to tell 'site down' from 'agents refused'."""
    async with httpx.AsyncClient(headers={"User-Agent": BROWSER_UA}, timeout=TIMEOUT, follow_redirects=True) as c:
        try:
            return (await c.get(url)).status_code
        except httpx.HTTPError:
            return 0


async def fresh_get(url: str) -> Page:
    """Fetch with a brand-new client: no cookies. This is what a human sees when they open a link."""
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True) as c:
        try:
            r = await c.get(url)
            return Page(str(r.url), r.status_code, r.text, r.headers.get("content-type", ""))
        except httpx.HTTPError:
            return Page(url, 0, "")
