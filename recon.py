"""Fetch signup page and extract forms, API hints, blockers."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

API_PATTERNS = [
    re.compile(r"""fetch\s*\(\s*['"]([^'"]+)['"]""", re.I),
    re.compile(r"""axios\.(?:post|put|get)\s*\(\s*['"]([^'"]+)['"]""", re.I),
    re.compile(r"""['"](/api/[^'"]+)['"]"""),
    re.compile(r"""['"](https?://[^'"]+/api/[^'"]+)['"]"""),
]
CAPTCHA_HINTS = {
    "recaptcha": re.compile(r"recaptcha|grecaptcha|6L[a-zA-Z0-9_-]{20,}", re.I),
    "hcaptcha": re.compile(r"hcaptcha", re.I),
    "turnstile": re.compile(r"turnstile|challenges\.cloudflare\.com", re.I),
}
CF_HINT = re.compile(r"cloudflare|cf-ray|__cf_bm", re.I)


@dataclass
class FormField:
    name: str
    type: str = "text"
    value: str = ""
    required: bool = False


@dataclass
class FormInfo:
    action: str
    method: str
    fields: list[FormField] = field(default_factory=list)


@dataclass
class ReconReport:
    url: str
    final_url: str
    site_base: str
    title: str
    status_code: int
    forms: list[FormInfo]
    api_candidates: list[str]
    script_urls: list[str]
    consent_snippets: list[str]
    captcha: list[str]
    cloudflare_likely: bool
    phone_field_hints: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class _FormParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base = base_url
        self.forms: list[FormInfo] = []
        self._form: FormInfo | None = None
        self._in_form = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "title" and not self.title:
            self._capture_title = True
        if tag == "form":
            self._in_form = True
            action = urljoin(self.base, ad.get("action") or self.base)
            method = (ad.get("method") or "GET").upper()
            self._form = FormInfo(action=action, method=method, fields=[])
        elif self._in_form and tag == "input" and self._form is not None:
            name = ad.get("name", "").strip()
            if name:
                self._form.fields.append(
                    FormField(
                        name=name,
                        type=ad.get("type", "text"),
                        value=ad.get("value", ""),
                        required="required" in ad,
                    )
                )
        elif self._in_form and tag == "textarea" and self._form is not None:
            name = ad.get("name", "").strip()
            if name:
                self._form.fields.append(FormField(name=name, type="textarea"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None
            self._in_form = False

    def handle_data(self, data: str) -> None:
        if getattr(self, "_capture_title", False):
            self.title += data.strip()

    def handle_endtag_title(self) -> None:  # noqa: N802 — not used; title via handle_data
        pass


def _site_base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _extract_scripts(html: str, base: str) -> list[str]:
    urls: list[str] = []
    for m in re.finditer(r"""<script[^>]+src=['"]([^'"]+)['"]""", html, re.I):
        urls.append(urljoin(base, m.group(1)))
    return urls[:15]


def _extract_apis(html: str, base: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pat in API_PATTERNS:
        for m in pat.finditer(html):
            u = m.group(1)
            if u.startswith("/"):
                u = urljoin(base, u)
            if u not in seen and ("api" in u.lower() or "submit" in u.lower() or "signup" in u.lower()):
                seen.add(u)
                found.append(u)
    for m in re.finditer(r"""['"](/api/[a-zA-Z0-9_./-]+)['"]""", html):
        u = urljoin(base, m.group(1))
        if u not in seen:
            seen.add(u)
            found.append(u)
    return found[:20]


def _consent_snippets(html: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"I agree to receive[^<]{20,500}", html, re.I):
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(s) > 40:
            out.append(s[:600])
    return list(dict.fromkeys(out))[:3]


def _phone_hints(forms: list[FormInfo], html: str) -> list[str]:
    hints: list[str] = []
    for f in forms:
        for fld in f.fields:
            n = fld.name.lower()
            if any(x in n for x in ("phone", "mobile", "tel", "sms")):
                hints.append(fld.name)
    for m in re.finditer(r"""['"]phone['"]\s*:\s*['"][^'"]*['"]""", html, re.I):
        hints.append(m.group(0)[:80])
    return list(dict.fromkeys(hints))


def analyze_url(url: str, *, timeout: int = 30, fetch_scripts: bool = True) -> ReconReport:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,*/*"})
    notes: list[str] = []

    r = s.get(url, timeout=timeout, allow_redirects=True)
    html = r.text or ""
    base = _site_base(r.url)

    parser = _FormParser(r.url)
    try:
        parser.feed(html)
    except Exception as e:
        notes.append(f"HTML parse warning: {e}")

    title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    title = (title_m.group(1).strip() if title_m else parser.title) or ""

    apis = _extract_apis(html, base)
    scripts = _extract_scripts(html, base)

    if fetch_scripts and scripts:
        extra_html = ""
        for su in scripts[:5]:
            try:
                sr = s.get(su, timeout=15)
                if sr.status_code == 200 and len(sr.text) < 500_000:
                    extra_html += sr.text
            except requests.RequestException:
                pass
        apis.extend(_extract_apis(extra_html, base))
        apis = list(dict.fromkeys(apis))[:25]

    captcha: list[str] = []
    for name, pat in CAPTCHA_HINTS.items():
        if pat.search(html):
            captcha.append(name)

    cf = bool(CF_HINT.search(html) or CF_HINT.search(str(r.headers)))

    return ReconReport(
        url=url,
        final_url=r.url,
        site_base=base,
        title=title,
        status_code=r.status_code,
        forms=parser.forms,
        api_candidates=apis,
        script_urls=scripts,
        consent_snippets=_consent_snippets(html),
        captcha=captcha,
        cloudflare_likely=cf,
        phone_field_hints=_phone_hints(parser.forms, html),
        notes=notes,
    )


def report_to_markdown(report: ReconReport) -> str:
    lines = [
        f"# Recon: {report.final_url}",
        f"- Title: {report.title}",
        f"- Status: {report.status_code}",
        f"- Cloudflare likely: {report.cloudflare_likely}",
        f"- Captcha: {', '.join(report.captcha) or 'none detected'}",
        "",
        "## Forms",
    ]
    if not report.forms:
        lines.append("(no HTML forms — likely SPA / JS submit)")
    for i, f in enumerate(report.forms, 1):
        lines.append(f"### Form {i}: {f.method} {f.action}")
        for fld in f.fields:
            lines.append(f"- `{fld.name}` type={fld.type} required={fld.required}")
    lines.extend(["", "## API candidates"])
    for u in report.api_candidates:
        lines.append(f"- {u}")
    if report.consent_snippets:
        lines.extend(["", "## Consent text"])
        for c in report.consent_snippets:
            lines.append(f"- {c[:200]}...")
    if report.phone_field_hints:
        lines.extend(["", "## Phone field hints", *[f"- {h}" for h in report.phone_field_hints]])
    return "\n".join(lines)


def save_report(report: ReconReport, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
