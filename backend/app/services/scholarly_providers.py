"""Live, concurrent scholarly discovery for one similarity run.

Provider metadata and permitted full text are processed transiently. This module
never creates Document records, writes source files to the upload directory, or
stores full-text source content in the database.
"""
from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from types import SimpleNamespace

import fitz
from flask import current_app

USER_AGENT = "AcaSift/0.16.0 External Scholarly Similarity (+https://acasift.onrender.com)"
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 8
MAX_SOURCE_CHARS = 900_000
MAX_PDF_PAGES = 100

ALLOWED_LICENSES = {
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "https://creativecommons.org/licenses/by/3.0/": "CC BY 3.0",
    "https://creativecommons.org/licenses/by/2.0/": "CC BY 2.0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
}

PROVIDERS = {
    "openalex": {"name": "OpenAlex", "kind": "discovery"},
    "crossref": {"name": "Crossref", "kind": "discovery"},
    "europe_pmc": {"name": "Europe PMC", "kind": "open_access_full_text"},
    "doaj": {"name": "DOAJ", "kind": "discovery"},
    "zenodo": {"name": "Zenodo", "kind": "open_access_full_text"},
    "semantic_scholar": {"name": "Semantic Scholar", "kind": "discovery"},
    "arxiv": {"name": "arXiv", "kind": "open_access_full_text"},
}

def _normalise_doi(value):
    value = str(value or "").strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return value.lower()[:255] or None


def _normalise_license(value):
    raw = str(value or "").strip()
    if not raw:
        return None, None
    lowered = raw.lower().rstrip("/")
    for url, name in ALLOWED_LICENSES.items():
        if lowered == url.lower().rstrip("/"):
            return name, url
    # Recognise exact versioned identifiers, but do not infer a version from
    # vague labels such as "CC BY" or from an open-access flag alone.
    aliases = {
        "cc-by-4.0": ("CC BY 4.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/4.0/"]),
        "cc-by-3.0": ("CC BY 3.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/3.0/"]),
        "cc-by-2.0": ("CC BY 2.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/2.0/"]),
        "cc0-1.0": ("CC0 1.0", ALLOWED_LICENSES["https://creativecommons.org/publicdomain/zero/1.0/"]),
    }
    key = lowered.replace("https://", "").replace("http://", "")
    key = key.replace("creativecommons.org/", "").strip("/")
    if key.startswith("licenses/"):
        key = key[len("licenses/"):]
    if key.startswith("publicdomain/zero/"):
        key = "cc0-" + key.rsplit("/", 1)[-1]
    elif key.startswith("by/"):
        key = "cc-by-" + key.rsplit("/", 1)[-1]
    if key in aliases:
        return aliases[key]
    labels = {
        "cc by 4.0": ("CC BY 4.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/4.0/"]),
        "cc by 3.0": ("CC BY 3.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/3.0/"]),
        "cc by 2.0": ("CC BY 2.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/2.0/"]),
        "creative commons attribution 4.0": ("CC BY 4.0", ALLOWED_LICENSES["https://creativecommons.org/licenses/by/4.0/"]),
    }
    if lowered in labels:
        return labels[lowered]
    if lowered in {"public domain", "public-domain", "pd"}:
        return "Public domain", ""
    return None, raw[:1000]


def _request_bytes(url, *, headers=None, max_bytes=2_000_000, timeout=HTTP_TIMEOUT_SECONDS, safe_external=False):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only HTTPS source URLs are accepted.")
    if safe_external:
        _assert_public_host(parsed.hostname)

    contact_email = current_app.config.get("ACQUISITION_CONTACT_EMAIL", "")
    user_agent = USER_AGENT + (f" mailto:{contact_email}" if contact_email else "")
    request_headers = {"User-Agent": user_agent, "Accept": "application/json, application/xml, application/pdf, text/plain;q=0.9, */*;q=0.5"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    opener = urllib.request.build_opener(_SafeRedirectHandler(safe_external=safe_external))
    for attempt in range(2):
        try:
            with opener.open(request, timeout=timeout) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    raise ValueError("The source file exceeds the configured acquisition size limit.")
                payload = response.read(max_bytes + 1)
                if len(payload) > max_bytes:
                    raise ValueError("The source file exceeds the configured acquisition size limit.")
                return payload, response.headers.get("Content-Type", "").lower(), response.geturl()
        except urllib.error.HTTPError as exc:
            if attempt == 0 and exc.code in {429, 503}:
                retry_after = exc.headers.get("Retry-After", "1")
                try:
                    delay = min(3, max(1, int(retry_after)))
                except (TypeError, ValueError):
                    delay = 1
                time.sleep(delay)
                continue
            raise
    raise RuntimeError("The scholarly source did not respond after a retry.")


def _assert_public_host(hostname):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except OSError as exc:
        raise ValueError("The document host could not be resolved safely.") from exc
    if not addresses:
        raise ValueError("The document host did not resolve to a public address.")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("The document host resolves to a non-public network address.")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, safe_external=False):
        super().__init__()
        self.safe_external = safe_external

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("A source redirected to an unsupported URL.")
        if self.safe_external:
            _assert_public_host(parsed.hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _json_request(url, headers=None):
    payload, _content_type, _final_url = _request_bytes(url, headers=headers, max_bytes=5_000_000)
    return json.loads(payload.decode("utf-8"))


def _authors(values):
    output = []
    for item in values or []:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = item.get("display_name") or item.get("name") or item.get("given") or ""
            if item.get("family") and item.get("given"):
                name = f"{item.get('given')} {item.get('family')}"
        else:
            name = ""
        if name:
            output.append(str(name)[:180])
    return output[:100]


def _year(value):
    try:
        if isinstance(value, list):
            value = value[0]
        if isinstance(value, dict):
            value = value.get("date-parts", [[None]])[0][0]
        if value is None:
            return None
        return int(str(value)[:4])
    except (TypeError, ValueError, IndexError):
        return None


def _safe_https_url(value, maximum=2000):
    value = str(value or "").strip()
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None
    return value[:maximum]


def _normalised_record(provider, provider_id, *, title, authors=None, year=None, journal=None,
                       doi=None, abstract=None, source_url=None, full_text_url=None,
                       full_text_format=None, license_value=None):
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    if not title:
        return None
    license_name, license_url = _normalise_license(license_value)
    rights_status = "eligible" if license_name else ("review_required" if license_value else "unknown")
    return {
        "provider": provider,
        "provider_id": str(provider_id or "")[:255],
        "title": title[:1000],
        "authors": _authors(authors),
        "year": _year(year),
        "journal": str(journal or "")[:500] or None,
        "doi": _normalise_doi(doi),
        "abstract": re.sub(r"\s+", " ", str(abstract or "")).strip()[:20000] or None,
        "source_url": _safe_https_url(source_url),
        "full_text_url": _safe_https_url(full_text_url),
        "full_text_format": full_text_format,
        "license_name": license_name,
        "license_url": license_url,
        "rights_status": rights_status,
    }


def _discover_openalex(query, limit, state):
    params = {
        "search": query,
        "filter": "is_oa:true",
        "per-page": min(limit, 25),
        "cursor": state.cursor or "*",
        "select": "id,doi,title,publication_year,authorships,primary_location,best_oa_location,open_access,ids,type",
    }
    api_key = current_app.config.get("OPENALEX_API_KEY", "")
    if state.cursor and state.cursor != "*" and not api_key:
        raise ValueError("OpenAlex requires an API key to continue beyond the first page. Add OPENALEX_API_KEY to Render environment variables.")
    contact = current_app.config.get("ACQUISITION_CONTACT_EMAIL", "")
    if contact:
        params["mailto"] = contact
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    data = _json_request(url, headers=headers)
    results = []
    for item in data.get("results", []):
        location = item.get("best_oa_location") or item.get("primary_location") or {}
        source = location.get("source") or {}
        license_value = location.get("license")
        results.append(_normalised_record(
            "openalex", item.get("id"), title=item.get("title"),
            authors=[(a.get("author") or {}).get("display_name") for a in item.get("authorships", [])],
            year=item.get("publication_year"), journal=source.get("display_name"), doi=item.get("doi"),
            source_url=location.get("landing_page_url"), full_text_url=location.get("pdf_url"),
            full_text_format="pdf", license_value=license_value,
        ))
    state.cursor = (data.get("meta") or {}).get("next_cursor")
    state.total_available = (data.get("meta") or {}).get("count")
    state.exhausted = not bool(state.cursor) or not results
    return [item for item in results if item]


def _discover_crossref(query, limit, state):
    params = {"query.bibliographic": query, "rows": min(limit, 25), "offset": state.offset,
              "select": "DOI,title,author,published-print,published-online,publisher,container-title,link,license,URL,type"}
    contact = current_app.config.get("ACQUISITION_CONTACT_EMAIL", "")
    if contact:
        params["mailto"] = contact
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    agent = USER_AGENT + (f" mailto:{contact}" if contact else "")
    data = _json_request(url, headers={"User-Agent": agent})
    results = []
    for item in (data.get("message") or {}).get("items", []):
        links = item.get("link") or []
        pdf_link = next((link.get("URL") for link in links if "pdf" in str(link.get("content-type", "")).lower()), None)
        licences = item.get("license") or []
        license_value = next((entry.get("URL") for entry in licences if entry.get("URL")), None)
        results.append(_normalised_record(
            "crossref", item.get("DOI"), title=(item.get("title") or [None])[0],
            authors=item.get("author"), year=item.get("published-print") or item.get("published-online"),
            journal=(item.get("container-title") or [None])[0], doi=item.get("DOI"),
            source_url=item.get("URL"), full_text_url=pdf_link, full_text_format="pdf",
            license_value=license_value,
        ))
    total = int((data.get("message") or {}).get("total-results") or 0)
    state.total_available = total
    state.offset += len(results)
    state.exhausted = not results or (total > 0 and state.offset >= total)
    return [item for item in results if item]


def _discover_europe_pmc(query, limit, state):
    params = {"query": f'({query}) AND OPEN_ACCESS:Y', "format": "json", "resultType": "core", "pageSize": min(limit, 25), "page": state.page}
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)
    data = _json_request(url)
    results = []
    for item in (data.get("resultList") or {}).get("result", []):
        pmcid = item.get("pmcid")
        full_text_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{urllib.parse.quote(pmcid)}/fullTextXML" if pmcid else None
        results.append(_normalised_record(
            "europe_pmc", item.get("id") or pmcid, title=item.get("title"),
            authors=[item.get("authorString")] if item.get("authorString") else [],
            year=item.get("firstPublicationDate"), journal=item.get("journalTitle"), doi=item.get("doi"),
            source_url=(f"https://europepmc.org/articles/{pmcid}" if pmcid else None),
            full_text_url=full_text_url, full_text_format="xml", license_value=None,
        ))
    total = int(data.get("hitCount") or data.get("hit_count") or 0)
    state.total_available = total
    state.page += 1
    state.exhausted = not results or (total > 0 and (state.page - 1) * min(limit, 25) >= total)
    return [item for item in results if item]


def _discover_doaj(query, limit, state):
    endpoint = "https://doaj.org/api/search/articles/" + urllib.parse.quote(query, safe="")
    url = endpoint + "?page=" + str(state.page) + "&pageSize=" + str(min(limit, 25))
    data = _json_request(url)
    results = []
    for result in data.get("results", []):
        bib = result.get("bibjson") or {}
        identifiers = bib.get("identifier") or []
        doi = next((item.get("id") for item in identifiers if str(item.get("type", "")).lower() == "doi"), None)
        links = bib.get("link") or []
        pdf_link = next((item.get("url") for item in links if "pdf" in str(item.get("content", "")).lower()), None)
        if not pdf_link and links:
            pdf_link = links[0].get("url")
        licences = bib.get("license") or []
        license_value = next((item.get("url") or item.get("type") for item in licences if item), None)
        results.append(_normalised_record(
            "doaj", result.get("id") or doi, title=bib.get("title"), authors=bib.get("author"),
            year=bib.get("year"), journal=(bib.get("journal") or {}).get("title"), doi=doi,
            source_url=next((item.get("url") for item in links if item.get("url")), None),
            full_text_url=pdf_link, full_text_format="pdf", license_value=license_value,
        ))
    total = int(data.get("total") or data.get("totalHits") or 0)
    state.total_available = total
    state.page += 1
    state.exhausted = not results or (total > 0 and (state.page - 1) * min(limit, 25) >= total)
    return [item for item in results if item]


def _discover_zenodo(query, limit, state):
    params = {"q": query, "size": min(limit, 25), "page": state.page, "type": "publication"}
    url = "https://zenodo.org/api/records?" + urllib.parse.urlencode(params)
    data = _json_request(url)
    results = []
    for item in ((data.get("hits") or {}).get("hits") or []):
        metadata = item.get("metadata") or {}
        license_data = metadata.get("license") or {}
        license_value = license_data.get("id") or license_data.get("url")
        files = item.get("files") or []
        pdf_file = next((file for file in files if str(file.get("key", "")).lower().endswith(".pdf")), None)
        file_links = (pdf_file or {}).get("links") or {}
        download_url = file_links.get("download") or file_links.get("self")
        results.append(_normalised_record(
            "zenodo", item.get("id") or item.get("doi"), title=metadata.get("title"),
            authors=metadata.get("creators"), year=metadata.get("publication_date"),
            journal=(metadata.get("journal") or {}).get("title"), doi=item.get("doi"),
            source_url=(item.get("links") or {}).get("html"), full_text_url=download_url,
            full_text_format="pdf", license_value=license_value,
        ))
    total_value = ((data.get("hits") or {}).get("total") or 0)
    total = int(total_value.get("value", 0) if isinstance(total_value, dict) else total_value)
    state.total_available = total
    state.page += 1
    state.exhausted = not results or (total > 0 and (state.page - 1) * min(limit, 25) >= total)
    return [item for item in results if item]


def _discover_semantic_scholar(query, limit, state):
    params = {"query": query, "limit": min(limit, 25), "offset": state.offset,
              "fields": "title,authors,year,abstract,url,externalIds,publicationVenue,openAccessPdf"}
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
    headers = {}
    api_key = current_app.config.get("SEMANTIC_SCHOLAR_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key
    data = _json_request(url, headers=headers)
    results = []
    for item in data.get("data", []):
        external = item.get("externalIds") or {}
        venue = item.get("publicationVenue") or {}
        oa_pdf = item.get("openAccessPdf") or {}
        results.append(_normalised_record(
            "semantic_scholar", item.get("paperId"), title=item.get("title"),
            authors=item.get("authors"), year=item.get("year"), journal=venue.get("name"),
            doi=external.get("DOI"), abstract=item.get("abstract"), source_url=item.get("url"),
            full_text_url=oa_pdf.get("url"), full_text_format="pdf", license_value=None,
        ))
    total = int(data.get("total") or 0)
    state.total_available = total
    state.offset += len(results)
    state.exhausted = not results or (total > 0 and state.offset >= total)
    return [item for item in results if item]


def _discover_arxiv(query, limit, state):
    params = {"search_query": f"all:{query}", "start": state.offset, "max_results": min(limit, 25), "sortBy": "relevance", "sortOrder": "descending"}
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    payload, _content_type, _final_url = _request_bytes(url, headers={"Accept": "application/atom+xml"}, max_bytes=5_000_000)
    root = ET.fromstring(payload)
    atom = "http://www.w3.org/2005/Atom"
    arxiv = "http://arxiv.org/schemas/atom"
    results = []
    for entry in root.findall(f"{{{atom}}}entry"):
        entry_id = entry.findtext(f"{{{atom}}}id")
        title = entry.findtext(f"{{{atom}}}title")
        authors = [node.findtext(f"{{{atom}}}name") for node in entry.findall(f"{{{atom}}}author")]
        published = entry.findtext(f"{{{atom}}}published")
        summary = entry.findtext(f"{{{atom}}}summary")
        pdf_url = None
        for link in entry.findall(f"{{{atom}}}link"):
            if link.attrib.get("title", "").lower() == "pdf":
                pdf_url = link.attrib.get("href")
                break
        license_node = entry.find(f"{{{arxiv}}}license")
        license_value = license_node.attrib.get("href") if license_node is not None else None
        if pdf_url and pdf_url.startswith("http://arxiv.org/"):
            pdf_url = "https://arxiv.org/" + pdf_url[len("http://arxiv.org/"):]
        results.append(_normalised_record(
            "arxiv", entry_id, title=title, authors=authors, year=published,
            doi=None, abstract=None, source_url=entry_id, full_text_url=pdf_url,
            full_text_format="pdf", license_value=license_value,
        ))
    total_node = root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    total = int(total_node.text) if total_node is not None and total_node.text else 0
    state.total_available = total
    state.offset += len(results)
    state.exhausted = not results or (total > 0 and state.offset >= total)
    return [item for item in results if item]


DISCOVERY_FUNCTIONS = {
    "openalex": _discover_openalex,
    "crossref": _discover_crossref,
    "europe_pmc": _discover_europe_pmc,
    "doaj": _discover_doaj,
    "zenodo": _discover_zenodo,
    "semantic_scholar": _discover_semantic_scholar,
    "arxiv": _discover_arxiv,
}



def _extract_xml_text(payload):
    root = ET.fromstring(payload)
    license_value = None
    for node in root.iter():
        if node.tag.split("}")[-1].lower() == "license":
            license_value = node.attrib.get("{http://www.w3.org/1999/xlink}href") or node.attrib.get("href")
            if license_value:
                break
    license_name, license_url = _normalise_license(license_value)
    if not license_name:
        raise ValueError("The article XML did not declare a recognised reuse licence.")

    body = next((node for node in root.iter() if node.tag.split("}")[-1].lower() == "body"), root)
    text = " ".join(part.strip() for part in body.itertext() if part and part.strip())
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    if len(text) < 300:
        raise ValueError("The full-text XML did not contain enough readable article text.")
    return text, license_value




class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "nav", "footer", "header", "noscript", "svg"}:
            self._ignored += 1
        elif tag.lower() in {"p", "div", "br", "li", "section", "article", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "nav", "footer", "header", "noscript", "svg"}:
            self._ignored = max(0, self._ignored - 1)
        elif tag.lower() in {"p", "div", "li", "section", "article"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


def _extract_html_text(payload):
    parser = _TextHTMLParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()[:MAX_SOURCE_CHARS]


def _extract_pdf_text(payload):
    with fitz.open(stream=payload, filetype="pdf") as pdf:
        parts = []
        total = 0
        for page_number, page in enumerate(pdf):
            if page_number >= MAX_PDF_PAGES:
                break
            chunk = page.get_text("text") or ""
            parts.append(chunk)
            total += len(chunk)
            if total >= MAX_SOURCE_CHARS:
                break
    return re.sub(r"\s+", " ", "\\n".join(parts)).strip()[:MAX_SOURCE_CHARS]


def fetch_permitted_full_text(record):
    """Fetch public full text in memory and return extracted text only.

    PDF/HTML content requires an exact recognised licence in provider metadata.
    Europe PMC XML is fetched only from its Open Access endpoint and is retained
    for comparison only if its article XML declares a recognised licence.
    """
    full_text_url = record.get("full_text_url")
    if not full_text_url:
        raise ValueError("No full-text location is available.")

    fmt = str(record.get("full_text_format") or "").lower()
    metadata_licence = record.get("license_name")
    metadata_licence_url = record.get("license_url")

    # XML Open Access endpoints can expose the article's exact licence inside
    # the XML itself, so permit a metadata-level licence probe for this format.
    if not metadata_licence and fmt != "xml":
        raise ValueError("No recognised reuse licence was identified; full text was not retrieved.")

    payload, content_type, final_url = _request_bytes(
        full_text_url,
        headers={"Accept": "application/pdf, application/xml, text/xml, text/html, text/plain;q=0.9"},
        max_bytes=max(1, int(current_app.config.get("MAX_EXTERNAL_DOWNLOAD_MB", 12))) * 1024 * 1024,
        timeout=HTTP_TIMEOUT_SECONDS,
        safe_external=True,
    )

    content_type = (content_type or "").split(";")[0].strip().lower()
    if payload.startswith(b"%PDF-") or content_type == "application/pdf":
        if not payload.startswith(b"%PDF-"):
            raise ValueError("The source declared PDF content but did not return a valid PDF.")
        if not metadata_licence:
            raise ValueError("No recognised reuse licence was identified for this PDF.")
        extracted = _extract_pdf_text(payload)
        licence_name = metadata_licence
        licence_url = metadata_licence_url
    elif "xml" in content_type or fmt == "xml" or payload.lstrip().startswith(b"<?xml"):
        extracted, xml_licence = _extract_xml_text(payload)
        licence_name, licence_url = _normalise_license(xml_licence)
        if not licence_name:
            raise ValueError("The article XML did not declare a recognised reuse licence.")
    elif content_type in {"text/html", "application/xhtml+xml"}:
        if not metadata_licence:
            raise ValueError("No recognised reuse licence was identified for this HTML source.")
        extracted = _extract_html_text(payload)
        licence_name = metadata_licence
        licence_url = metadata_licence_url
    elif content_type.startswith("text/"):
        if not metadata_licence:
            raise ValueError("No recognised reuse licence was identified for this text source.")
        extracted = payload.decode("utf-8", errors="replace")[:MAX_SOURCE_CHARS]
        licence_name = metadata_licence
        licence_url = metadata_licence_url
    else:
        raise ValueError("The source did not return a supported full-text format.")

    extracted = re.sub(r"\s+", " ", extracted or "").strip()
    if len(extracted) < 300:
        raise ValueError("The accessible source did not contain enough extractable text.")

    return {
        "text": extracted,
        "final_url": final_url,
        "license_name": licence_name,
        "license_url": licence_url,
    }


def targeted_queries(submitted_text, document_title=None, max_queries=3):
    """Derive short title/keyword queries; never transmit the full submitted document."""
    text = str(submitted_text or "")
    stop_words = {
        "about", "after", "again", "also", "among", "because", "before", "being",
        "between", "both", "could", "during", "each", "from", "have", "having",
        "into", "more", "most", "other", "over", "same", "should", "some", "such",
        "than", "that", "their", "there", "these", "they", "this", "those",
        "through", "under", "using", "very", "were", "what", "when", "where",
        "which", "while", "with", "within", "would", "your", "study", "research",
        "paper", "results", "method", "methods", "analysis", "objective",
        "objectives", "chapter", "abstract", "introduction", "conclusion",
    }
    words = re.findall(r"\b[a-zA-Z][a-zA-Z-]{3,}\b", text[:250_000].lower())
    frequencies = {}
    for word in words:
        if word not in stop_words:
            frequencies[word] = frequencies.get(word, 0) + 1
    ranked_words = sorted(frequencies, key=lambda word: (-frequencies[word], word))
    queries = []

    # Use the contributor-supplied document title, not an arbitrary first line
    # from the document body, to avoid transmitting unrelated cover-page content.
    title = re.sub(r"\s+", " ", str(document_title or "")).strip()
    if len(title.split()) >= 3 and len(title) <= 180:
        queries.append(title)

    top_terms = ranked_words[:8]
    if len(top_terms) >= 4:
        queries.append(" ".join(top_terms[:8])[:180])

    bigram_counts = {}
    filtered = [word for word in words if word not in stop_words]
    for left, right in zip(filtered, filtered[1:]):
        if left == right:
            continue
        phrase = f"{left} {right}"
        bigram_counts[phrase] = bigram_counts.get(phrase, 0) + 1
    top_phrases = sorted(bigram_counts, key=lambda phrase: (-bigram_counts[phrase], phrase))[:5]
    if top_phrases:
        queries.append(" ".join(top_phrases[:4])[:180])

    deduped = []
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip()
        if query and query.casefold() not in {item.casefold() for item in deduped}:
            deduped.append(query)
    return deduped[:max(1, int(max_queries))]


def _candidate_key(record):
    doi = _normalise_doi(record.get("doi"))
    if doi:
        return "doi:" + doi
    title = re.sub(r"[^a-z0-9]+", " ", str(record.get("title") or "").lower()).strip()
    return "title:" + title[:250]


def _merge_candidates(records):
    merged = {}
    for record in records:
        if not record:
            continue
        key = _candidate_key(record)
        if not key or key == "title:":
            continue
        if key not in merged:
            item = dict(record)
            item["providers"] = [record.get("provider")] if record.get("provider") else []
            merged[key] = item
            continue
        item = merged[key]
        if record.get("provider") and record["provider"] not in item["providers"]:
            item["providers"].append(record["provider"])
        for field in ("authors", "year", "journal", "doi", "abstract", "source_url"):
            if not item.get(field) and record.get(field):
                item[field] = record[field]
        # Keep the reuse licence paired with the exact full-text location that
        # supplied that licence. Do not transfer a licence from one provider's
        # landing page to another provider's unrelated file URL.
        if record.get("full_text_url") and (
            not item.get("full_text_url")
            or (record.get("license_name") and not item.get("license_name"))
        ):
            item["full_text_url"] = record["full_text_url"]
            item["full_text_format"] = record.get("full_text_format")
            item["license_name"] = record.get("license_name")
            item["license_url"] = record.get("license_url")
            item["rights_status"] = record.get("rights_status", "unknown")
            item["provider"] = record.get("provider") or item.get("provider")
    return list(merged.values())


def discover_scholarly_sources(submitted_text, document_title=None, max_sources=None):
    """Search all configured scholarly providers concurrently using targeted queries."""
    app = current_app._get_current_object()
    queries = targeted_queries(submitted_text, document_title=document_title)
    max_sources = max_sources or int(app.config.get("MAX_EXTERNAL_SOURCES", 24))
    max_sources = min(max(1, int(max_sources)), 40)

    tasks = [
        (provider, query)
        for provider in DISCOVERY_FUNCTIONS
        for query in queries
    ]
    raw_records = []
    provider_status = {
        provider: {"queries_attempted": len(queries), "queries_succeeded": 0,
                   "records_returned": 0, "errors": []}
        for provider in DISCOVERY_FUNCTIONS
    }

    def search_one(provider, query):
        with app.app_context():
            state = SimpleNamespace(
                cursor="*" if provider == "openalex" else None,
                offset=0,
                page=1,
                total_available=None,
                exhausted=False,
            )
            function = DISCOVERY_FUNCTIONS[provider]
            return function(query, 5, state)

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(tasks)))) as executor:
        future_map = {
            executor.submit(search_one, provider, query): (provider, query)
            for provider, query in tasks
        }
        for future in as_completed(future_map):
            provider, query = future_map[future]
            try:
                records = future.result()
                provider_status[provider]["queries_succeeded"] += 1
                provider_status[provider]["records_returned"] += len(records or [])
                raw_records.extend(records or [])
            except Exception as exc:
                provider_status[provider]["errors"].append(type(exc).__name__)
                app.logger.warning(
                    "External scholarly discovery failed for provider %s (query %s): %s",
                    provider, query[:80], type(exc).__name__,
                )

    candidates = _merge_candidates(raw_records)
    # Prefer candidates with a known reusable licence and an actual full-text URL.
    candidates.sort(
        key=lambda item: (
            bool(item.get("license_name") and item.get("full_text_url")),
            bool(item.get("full_text_url")),
            bool(item.get("doi")),
            item.get("year") or 0,
        ),
        reverse=True,
    )
    return {
        "queries": queries,
        "providers": provider_status,
        "raw_results_count": len(raw_records),
        "sources_discovered": len(candidates),
        "sources": candidates[:max_sources],
    }


def retrieve_sources_concurrently(candidates, max_downloads=None):
    """Retrieve only permitted public full text, concurrently and in memory."""
    app = current_app._get_current_object()
    max_downloads = max_downloads or int(app.config.get("MAX_EXTERNAL_DOWNLOADS", 8))
    max_downloads = min(max(1, int(max_downloads)), 15)

    eligible = []
    for candidate in candidates:
        fmt = str(candidate.get("full_text_format") or "").lower()
        if candidate.get("license_name") or fmt == "xml":
            if candidate.get("full_text_url"):
                eligible.append(candidate)
        if len(eligible) >= max_downloads:
            break

    def retrieve_one(candidate):
        with app.app_context():
            result = fetch_permitted_full_text(candidate)
            return candidate, result

    retrieved = []
    failures = []
    if not eligible:
        return retrieved, failures

    with ThreadPoolExecutor(max_workers=min(4, len(eligible))) as executor:
        future_map = {
            executor.submit(retrieve_one, candidate): candidate
            for candidate in eligible
        }
        for future in as_completed(future_map):
            candidate = future_map[future]
            try:
                source, result = future.result()
                retrieved.append((source, result))
            except Exception as exc:
                failures.append({
                    "title": candidate.get("title", "Untitled source"),
                    "provider": candidate.get("provider"),
                    "reason": str(exc)[:300],
                })
    return retrieved, failures


def run_live_scholarly_discovery(submitted_text, document_title=None, max_sources=None, max_downloads=None):
    discovery = discover_scholarly_sources(
        submitted_text, document_title=document_title, max_sources=max_sources
    )
    retrieved, failures = retrieve_sources_concurrently(
        discovery["sources"],
        max_downloads=max_downloads,
    )
    providers = discovery["providers"]
    all_queries_failed = bool(providers) and all(
        value["queries_succeeded"] == 0 for value in providers.values()
    )
    some_queries_failed = any(
        value["queries_succeeded"] < value["queries_attempted"]
        for value in providers.values()
    )
    status = "unavailable" if all_queries_failed else ("partial" if some_queries_failed or failures else "completed")
    return {
        **discovery,
        "retrieved_sources": retrieved,
        "sources_downloaded": len(retrieved),
        "retrieval_failures": failures[:20],
        "status": status,
        "full_text_retained": False,
    }
