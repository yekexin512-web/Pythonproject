from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .date_utils import parse_date, parse_job_opening_id
from .models import Job


DETAIL_URL = "https://inspira.un.org/psc/UNCAREERS/EMPLOYEE/HRMS/c/UN_CUSTOMIZATIONS.UN_JOB_DETAIL.GBL?JobOpeningId={job_id}"


def fetch_internship_jobs(search_url: str, headless: bool = True) -> list[Job]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        page.goto(search_url, wait_until="domcontentloaded", timeout=90_000)
        if "jobopening" not in page.url.lower():
            _try_search(page)
        pages = _collect_result_pages(page)
        current_url = page.url
        browser.close()
    jobs_by_id: dict[str, Job] = {}
    for html, visible_text in pages:
        jobs = parse_jobs_from_visible_text(visible_text, html, current_url) or parse_jobs_from_html(html, current_url)
        for job in jobs:
            jobs_by_id[job.job_opening_id] = job
    return sorted(jobs_by_id.values(), key=lambda job: (job.deadline_date is None, job.deadline_date or job.posted_date, job.title))


def _collect_result_pages(page, max_pages: int = 50) -> list[tuple[str, str]]:
    pages: list[tuple[str, str]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    for _ in range(max_pages):
        visible_text = _wait_for_results(page)
        html = page.content()
        jobs = parse_jobs_from_visible_text(visible_text, html, page.url) or parse_jobs_from_html(html, page.url)
        signature = tuple(job.job_opening_id for job in jobs)
        if signature in seen_signatures:
            break
        seen_signatures.add(signature)
        pages.append((html, visible_text))
        next_link = _next_page_link(page)
        if next_link is None:
            break
        try:
            next_link.click(timeout=5_000)
            page.wait_for_timeout(2_000)
        except Exception:
            break
    return pages


def _wait_for_results(page) -> str:
    page.wait_for_timeout(3_000)
    body_text = page.locator("body").inner_text(timeout=10_000)
    if "403 ERROR" in body_text or "Request blocked" in body_text:
        raise RuntimeError("UN Careers 返回 403，当前网络或浏览器环境被 CloudFront 拦截。")
    if "Loading..." in body_text:
        try:
            page.get_by_text("View Job Description").first.wait_for(timeout=30_000)
            body_text = page.locator("body").inner_text(timeout=10_000)
        except Exception:
            pass
    return body_text


def _next_page_link(page):
    links = page.locator("a.page-link")
    for index in range(links.count()):
        link = links.nth(index)
        try:
            if link.inner_text(timeout=1_000).strip() not in {"»", "›", "Next"}:
                continue
            parent_class = link.locator("xpath=..").get_attribute("class") or ""
            if "disabled" not in parent_class.lower():
                return link
        except Exception:
            continue
    return None


def _try_search(page) -> None:
    for selector in ("select[name*='Category' i]", "select[id*='Category' i]", "select"):
        try:
            selects = page.locator(selector)
            for index in range(selects.count()):
                select = selects.nth(index)
                options = select.locator("option")
                for option_index in range(options.count()):
                    option = options.nth(option_index)
                    option_text = option.inner_text(timeout=2_000).strip()
                    if re.search(r"\bInternship\b", option_text, re.IGNORECASE):
                        option_value = option.get_attribute("value")
                        select.select_option(value=option_value) if option_value else select.select_option(label=option_text)
                        break
        except Exception:
            continue

    for text in ("Search", "Start search", "Submit"):
        try:
            button = page.get_by_role("button", name=re.compile(text, re.IGNORECASE)).first
            if button.count() > 0:
                button.click(timeout=5_000)
                page.wait_for_load_state("networkidle", timeout=30_000)
                return
        except PlaywrightTimeoutError:
            return
        except Exception:
            continue


def parse_jobs_from_html(html: str, base_url: str) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    line_jobs = _parse_jobs_from_lines(soup, base_url)
    if line_jobs:
        return line_jobs

    jobs_by_id: dict[str, Job] = {}
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        job_id = _job_id_from_url(href) or parse_job_opening_id(link.get_text(" ", strip=True))
        if not job_id:
            continue
        container = _job_container(link)
        text = container.get_text("\n", strip=True)
        if "intern" not in text.lower() and "intern" not in link.get_text(" ", strip=True).lower():
            continue

        fields = _extract_fields(text)
        title = _extract_title(link, container, job_id)
        apply_url = _normalize_apply_url(href, base_url, job_id)
        jobs_by_id[job_id] = Job(
            job_opening_id=job_id,
            title=title,
            department=fields.get("department", ""),
            location=fields.get("location", ""),
            posted_date=parse_date(fields.get("posted_date")),
            deadline_date=parse_date(fields.get("deadline_date")),
            apply_url=apply_url,
        )
    return sorted(jobs_by_id.values(), key=lambda job: (job.deadline_date is None, job.deadline_date or job.posted_date, job.title))


def parse_jobs_from_visible_text(visible_text: str, html: str, base_url: str) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    link_by_id: dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        job_id = _job_id_from_url(str(link["href"]))
        if job_id:
            link_by_id[job_id] = _normalize_apply_url(str(link["href"]), base_url, job_id)
    return _parse_jobs_from_lines_text(visible_text, base_url, link_by_id)


def _parse_jobs_from_lines(soup: BeautifulSoup, base_url: str) -> list[Job]:
    link_by_id: dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        job_id = _job_id_from_url(str(link["href"]))
        if job_id:
            link_by_id[job_id] = _normalize_apply_url(str(link["href"]), base_url, job_id)

    return _parse_jobs_from_lines_text(soup.get_text("\n", strip=True), base_url, link_by_id)


def _parse_jobs_from_lines_text(text: str, base_url: str, link_by_id: dict[str, str]) -> list[Job]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    jobs_by_id: dict[str, Job] = {}
    for index, line in enumerate(lines):
        match = re.fullmatch(r"Job ID\s*:\s*(\d+)", line, flags=re.IGNORECASE)
        if not match or index == 0:
            continue
        job_id = match.group(1)
        title = _clean_label(lines[index - 1], job_id)
        fields = _fields_after_job_id(lines, index)
        if "internship" not in fields.get("category", "").lower() and "intern" not in title.lower():
            continue
        jobs_by_id[job_id] = Job(
            job_opening_id=job_id,
            title=title,
            department=fields.get("department", ""),
            location=fields.get("location", ""),
            posted_date=parse_date(fields.get("posted_date")),
            deadline_date=parse_date(fields.get("deadline_date")),
            apply_url=link_by_id.get(job_id, urljoin(base_url, f"/jobSearchDescription/{job_id}?language=en")),
        )
    return sorted(jobs_by_id.values(), key=lambda job: (job.deadline_date is None, job.deadline_date or job.posted_date, job.title))


def _fields_after_job_id(lines: list[str], job_id_index: int) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines[job_id_index + 1 : job_id_index + 12]:
        if line.lower() == "view job description":
            break
        label, separator, value = line.partition(":")
        if not separator:
            continue
        normalized = label.strip().lower()
        value = value.strip()
        if normalized == "category and level":
            fields["category"] = value
        elif normalized == "duty station":
            fields["location"] = value
        elif normalized == "department/office":
            fields["department"] = value
        elif normalized == "date posted":
            fields["posted_date"] = value
        elif normalized == "deadline":
            fields["deadline_date"] = value
    return fields


def _job_id_from_url(url: str) -> str | None:
    path_match = re.search(r"/jobSearchDescription/(\d+)", url, flags=re.IGNORECASE)
    if path_match:
        return path_match.group(1)
    query = parse_qs(urlparse(url).query)
    for key in ("JobOpeningId", "jobOpeningId", "jobopeningid"):
        if key in query and query[key]:
            return query[key][0]
    return parse_job_opening_id(url)


def _normalize_apply_url(href: str, base_url: str, job_id: str) -> str:
    if "/jobSearchDescription/" in href:
        return urljoin(base_url, href)
    if "JobOpeningId" in href or "jobopeningid" in href.lower():
        return urljoin(base_url, href)
    return urljoin(base_url, f"/jobSearchDescription/{job_id}?language=en")


def _job_container(link: Tag) -> Tag:
    for parent in link.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"tr", "li", "article"}:
            return parent
        class_text = " ".join(parent.get("class", []))
        if re.search(r"(job|opening|result|card|vacancy)", class_text, re.IGNORECASE):
            return parent
    return link.parent if isinstance(link.parent, Tag) else link


def _extract_title(link: Tag, container: Tag, job_id: str) -> str:
    link_text = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
    if link_text and not re.fullmatch(r"\d+", link_text) and "view job description" not in link_text.lower():
        return _clean_label(link_text, job_id)

    lines = [line.strip() for line in container.get_text("\n", strip=True).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if parse_job_opening_id(line) == job_id and index > 0:
            return _clean_label(lines[index - 1], job_id)

    for heading in container.find_all(re.compile("^h[1-6]$")):
        text = heading.get_text(" ", strip=True)
        if text:
            return _clean_label(text, job_id)

    for line in lines:
        if "intern" in line.lower():
            return _clean_label(line, job_id)
    return f"Internship {job_id}"


def _clean_label(value: str, job_id: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" -")
    text = re.sub(rf"\b{re.escape(job_id)}\b", "", text).strip(" -")
    return text or f"Internship {job_id}"


def _extract_fields(text: str) -> dict[str, str]:
    compact = re.sub(r"[ \t]+", " ", text)
    fields: dict[str, str] = {}
    patterns = {
        "department": r"(?:Department/Office|Department|Org\.?\s*Setting|Office|Organization)\s*:?\s*([^\n]+)",
        "location": r"(?:Location|Duty Station)\s*:?\s*([^\n]+)",
        "posted_date": r"(?:Posted|Posting Date|Publication Date|Date Posted)\s*:?\s*([^\n]+)",
        "deadline_date": r"(?:Deadline|Application Deadline|Closing Date|Expires)\s*:?\s*([^\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match:
            fields[key] = match.group(1).strip(" -")
    lines = [line.strip(" :\t") for line in compact.splitlines() if line.strip(" :\t")]
    line_labels = {
        "department": {"department/office", "department", "office", "organization"},
        "location": {"location", "duty station"},
        "posted_date": {"posted", "posting date", "publication date", "date posted"},
        "deadline_date": {"deadline", "application deadline", "closing date", "expires"},
    }
    for index, line in enumerate(lines[:-1]):
        normalized = line.lower()
        for key, labels in line_labels.items():
            if key not in fields and normalized in labels:
                fields[key] = lines[index + 1]
    return fields
