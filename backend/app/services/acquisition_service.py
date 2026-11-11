"""Multi-source scholarly discovery and permission-aware full-text ingestion.

The service deliberately separates metadata discovery from comparison-corpus
admission. A record is never indexed as a global reference unless its exact
source record provides a recognised reuse licence and the downloaded content
passes format, size, extraction and duplicate checks.
"""

import hashlib
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
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import and_, or_

from app.extensions import db
from app.models import Document
from app.reference_models import ReferenceEntry
from app.acquisition_models import AcquisitionJob, AcquisitionSearchState, ScholarlyRecord
from app.services.document_service import calculate_sha256, extract_text, make_storage_filename
from app.services.reference_service import register_reference_entry

USER_AGENT = "AcaSiftReferenceAcquisition/0.14.0 (+https://acasift.onrender.com)"
MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
MAX_RECORDS_PER_RUN = 25
MAX_DOWNLOADS_PER_RUN = 2
HTTP_TIMEOUT_SECONDS = 8

PROVIDERS = {
    "openalex": {"name": "OpenAlex", "kind": "discovery", "configured": True},
    "crossref": {"name": "Crossref", "kind": "discovery", "configured": True},
    "europe_pmc": {"name": "Europe PMC", "kind": "full_text", "configured": True},
    "doaj": {"name": "DOAJ", "kind": "discovery", "configured": True},
    "zenodo": {"name": "Zenodo", "kind": "full_text", "configured": True},
    "semantic_scholar": {"name": "Semantic Scholar", "kind": "discovery", "configured": True},
    "arxiv": {"name": "arXiv", "kind": "discovery", "configured": True},
}

ALLOWED_LICENSES = {
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "https://creativecommons.org/licenses/by/3.0/": "CC BY 3.0",
    "https://creativecommons.org/licenses/by/2.0/": "CC BY 2.0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
}


def utc_now():
    return datetime.now(timezone.utc)


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


def _canonical_key(doi, title, year):
    if doi:
        digest = hashlib.sha256(doi.lower().encode("utf-8")).hexdigest()
        return "doi:" + digest
    normal_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    digest = hashlib.sha256(f"{normal_title}|{year or ''}".encode("utf-8")).hexdigest()
    return "title:" + digest


def _request_bytes(url, *, headers=None, max_bytes=2_000_000, timeout=HTTP_TIMEOUT_SECONDS, safe_external=False):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
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
        "source_url": source_url,
        "full_text_url": full_text_url,
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


def _upsert_scholarly_record(item):
    canonical_key = _canonical_key(item.get("doi"), item["title"], item.get("year"))
    record = ScholarlyRecord.query.filter_by(canonical_key=canonical_key).first()
    is_new = record is None
    if record is None:
        record = ScholarlyRecord(canonical_key=canonical_key, title=item["title"], primary_provider=item["provider"])
        db.session.add(record)
        db.session.flush()
    provider_ids = json.loads(record.provider_ids_json or "[]")
    provider_identity = {"provider": item["provider"], "id": item.get("provider_id")}
    if provider_identity not in provider_ids:
        provider_ids.append(provider_identity)
    record.provider_ids_json = json.dumps(provider_ids[:50], ensure_ascii=False)
    record.doi = record.doi or item.get("doi")
    record.title = item["title"] or record.title
    record.authors_json = json.dumps(item.get("authors") or [], ensure_ascii=False)
    # Abstracts are not needed for comparison and may carry separate reuse
    # restrictions. Retain bibliographic metadata only in this first release.
    record.abstract_text = None
    record.publication_year = record.publication_year or item.get("year")
    record.journal_title = record.journal_title or item.get("journal")
    record.source_url = record.source_url or item.get("source_url")
    record.full_text_url = record.full_text_url or item.get("full_text_url")
    record.full_text_format = record.full_text_format or item.get("full_text_format")
    record.license_name = record.license_name or item.get("license_name")
    record.license_url = record.license_url or item.get("license_url")
    if item.get("rights_status") == "eligible":
        record.rights_status = "eligible"
    elif item.get("rights_status") == "review_required" and record.rights_status == "unknown":
        record.rights_status = "review_required"
    record.last_seen_at = utc_now()
    if record.document_id:
        record.status = "indexed"
    elif (record.rights_status == "eligible" and record.full_text_url) or (
        record.full_text_format == "xml" and record.full_text_url and record.rights_status == "unknown"
    ):
        record.status = "eligible"
    else:
        record.status = "metadata_only"
    return record, is_new


def _extract_xml_text(payload):
    root = ET.fromstring(payload)
    body = next((node for node in root.iter() if node.tag.split("}")[-1].lower() == "body"), root)
    text = " ".join(part.strip() for part in body.itertext() if part and part.strip())
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    if len(text) < 300:
        raise ValueError("The full-text XML did not contain enough readable article text.")
    license_value = None
    for node in root.iter():
        if node.tag.split("}")[-1].lower() == "license":
            license_value = node.attrib.get("{http://www.w3.org/1999/xlink}href") or node.attrib.get("href")
            if license_value:
                break
    return text, license_value


def _download_and_index(record, admin_user_id):
    if record.document_id:
        return "already_indexed"
    if not record.full_text_url:
        return "metadata_only"

    payload, content_type, final_url = _request_bytes(
        record.full_text_url,
        headers={"Accept": "application/pdf, application/xml, text/xml, text/plain;q=0.9"},
        max_bytes=MAX_DOWNLOAD_BYTES,
        timeout=HTTP_TIMEOUT_SECONDS,
        safe_external=True,
    )
    file_type = None
    file_bytes = payload
    filename = ""
    if payload.startswith(b"%PDF-") or "application/pdf" in content_type or str(final_url).lower().split("?")[0].endswith(".pdf"):
        if not payload.startswith(b"%PDF-"):
            raise ValueError("The source claimed to provide a PDF but the downloaded file is not a PDF.")
        file_type = "pdf"
        filename = f"acasift-reference-{record.record_id}.pdf"
    elif "xml" in content_type or payload.lstrip().startswith(b"<?xml") or record.full_text_format == "xml":
        text, xml_license = _extract_xml_text(payload)
        licence_name, licence_url = _normalise_license(xml_license)
        if not licence_name:
            record.rights_status = "review_required" if xml_license else "unknown"
            record.status = "metadata_only"
            if xml_license:
                record.license_url = xml_license[:1000]
            return "metadata_only"
        record.license_name = licence_name
        record.license_url = licence_url or record.license_url
        file_type = "txt"
        file_bytes = text.encode("utf-8")
        filename = f"acasift-reference-{record.record_id}.txt"
    else:
        raise ValueError("The downloaded content is not a supported PDF or full-text XML document.")

    # Require an exact recognised licence before placing any full text in the
    # active global comparison bank. An OA flag or free PDF URL is insufficient.
    licence_name, licence_url = _normalise_license(record.license_url or record.license_name)
    if not licence_name:
        record.rights_status = "review_required" if record.license_name or record.license_url else "unknown"
        record.status = "metadata_only"
        return "metadata_only"

    extracted = extract_text(filename, file_bytes)
    digest = calculate_sha256(file_bytes)
    duplicate = Document.query.filter_by(file_hash=digest).first()
    if duplicate:
        existing_entry = ReferenceEntry.query.filter_by(document_id=duplicate.document_id, scope_key="global").first()
        if existing_entry and existing_entry.status == "active" and existing_entry.rights_verified:
            record.document_id = duplicate.document_id
            record.status = "indexed"
            record.rights_status = "eligible"
            return "already_indexed"
        raise ValueError("The downloaded file duplicates an existing document whose global reuse status is not verified.")

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    storage_name = make_storage_filename(filename)
    storage_path = os.path.join(upload_folder, storage_name)
    with open(storage_path, "wb") as stored_file:
        stored_file.write(file_bytes)

    document = Document(
        user_id=admin_user_id,
        title=record.title[:255],
        original_filename=filename[:255],
        storage_path=storage_name,
        file_type=file_type,
        document_type="reference",
        extracted_text=extracted,
        file_hash=digest,
        workspace_id=None,
        visibility_scope="platform",
        processing_status="processed",
    )
    db.session.add(document)
    db.session.flush()
    register_reference_entry(
        document,
        "global",
        admin_user_id,
        status="active",
        provenance_type="api_acquired",
        source_title=record.title,
        source_url=record.source_url,
        doi=record.doi,
        rights_basis="public_domain" if licence_name == "Public domain" else "open_license",
        license_name=licence_name,
        license_url=licence_url or None,
        rights_notes=(
            f"Acquired through {record.primary_provider}. An exact recognised licence was identified in source metadata or article XML. "
            "This is automated licence verification, not a representation that every separately credited third-party element is covered. "
            "AcaSift retained source attribution and DOI; administrator review of any separately credited material remains necessary."
        ),
        rights_verified=True,
        verified_by_user_id=None,
        verified_at=utc_now(),
    )
    record.document_id = document.document_id
    record.license_name = licence_name
    record.license_url = licence_url or None
    record.rights_status = "eligible"
    record.status = "indexed"
    return "indexed"


def _attempt_full_text(record, admin_user_id):
    """Attempt one permitted full-text import and persist bounded retry state."""
    record.download_attempts = int(record.download_attempts or 0) + 1
    db.session.commit()
    try:
        result = _download_and_index(record, admin_user_id)
        record.last_error = None
        db.session.commit()
        return result, None
    except Exception as exc:
        db.session.rollback()
        record = db.session.get(ScholarlyRecord, record.record_id)
        record.last_error = str(exc)[:2000]
        if record.download_attempts >= 3:
            record.status = "failed"
        db.session.commit()
        return "failed", str(exc)


def _pending_full_text_query():
    permission_or_xml_probe = or_(
        ScholarlyRecord.rights_status == "eligible",
        and_(
            ScholarlyRecord.rights_status == "unknown",
            ScholarlyRecord.full_text_format == "xml",
        ),
    )
    return ScholarlyRecord.query.filter(
        permission_or_xml_probe,
        ScholarlyRecord.status == "eligible",
        ScholarlyRecord.document_id.is_(None),
        ScholarlyRecord.full_text_url.isnot(None),
        ScholarlyRecord.download_attempts < 3,
    )


def _pending_full_text_records(provider, limit):
    return _pending_full_text_query(provider).order_by(
        ScholarlyRecord.created_at.asc()
    ).limit(limit).all()


def _job_payload(job):
    return {
        "id": job.job_id,
        "provider": job.provider,
        "query": job.query,
        "requested_limit": job.requested_limit,
        "status": job.status,
        "discovered_count": job.discovered_count,
        "new_records_count": job.new_records_count,
        "duplicate_count": job.duplicate_count,
        "indexed_count": job.indexed_count,
        "metadata_only_count": job.metadata_only_count,
        "failed_count": job.failed_count,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def acquisition_dashboard():
    from sqlalchemy import and_, func, or_

    record_counts = {
        row[0]: row[1]
        for row in db.session.query(ScholarlyRecord.status, func.count(ScholarlyRecord.record_id)).group_by(ScholarlyRecord.status).all()
    }
    jobs = AcquisitionJob.query.order_by(AcquisitionJob.created_at.desc()).limit(20).all()
    records = ScholarlyRecord.query.order_by(ScholarlyRecord.updated_at.desc()).limit(20).all()
    searches = AcquisitionSearchState.query.order_by(AcquisitionSearchState.updated_at.desc()).limit(20).all()
    providers = []
    for key, details in PROVIDERS.items():
        if key == "openalex":
            configured = True
        else:
            configured = True
        providers.append({"id": key, **details, "configured": configured})
    return {
        "counts": {
            "total": sum(record_counts.values()),
            "indexed": record_counts.get("indexed", 0),
            "metadata_only": record_counts.get("metadata_only", 0),
            "eligible": record_counts.get("eligible", 0),
            "failed": record_counts.get("failed", 0),
            "review_required": record_counts.get("review_required", 0),
            "reference_bank_count": ReferenceEntry.query.filter_by(
                scope="global", status="active", rights_verified=True
            ).count(),
        },
        "providers": providers,
        "jobs": [_job_payload(job) for job in jobs],
        "searches": [{
            "provider": state.provider,
            "query": state.query,
            "total_available": state.total_available,
            "exhausted": bool(state.exhausted),
            "next_page": state.page if state.provider in {"europe_pmc", "doaj", "zenodo"} else None,
            "next_offset": state.offset if state.provider in {"crossref", "semantic_scholar", "arxiv"} else None,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        } for state in searches],
        "records": [{
            "id": record.record_id,
            "title": record.title,
            "doi": record.doi,
            "provider": record.primary_provider,
            "year": record.publication_year,
            "rights_status": record.rights_status,
            "status": record.status,
            "document_id": record.document_id,
        } for record in records],
    }


def run_acquisition_job(job_id):
    job = db.session.get(AcquisitionJob, job_id)
    if not job:
        raise ValueError("The acquisition job was not found.")
    if job.status == "running":
        raise ValueError("This acquisition job is already running.")
    discover = DISCOVERY_FUNCTIONS.get(job.provider)
    if not discover:
        raise ValueError("The selected scholarly source is not supported.")

    job.status = "running"
    job.started_at = utc_now()
    job.error_message = None
    db.session.commit()

    try:
        state = db.session.get(AcquisitionSearchState, job.search_state_id) if job.search_state_id else None
        if not state:
            raise ValueError("The resumable search state is missing. Start a new search.")
        pending = _pending_full_text_records(job.provider, MAX_DOWNLOADS_PER_RUN)
        if pending:
            for record in pending:
                result, error = _attempt_full_text(record, job.requested_by_user_id)
                if result in {"indexed", "already_indexed"}:
                    job.indexed_count += 1
                elif result == "metadata_only":
                    job.metadata_only_count += 1
                if error:
                    job.failed_count += 1
            remaining = _pending_full_text_query().count()
            job.status = "partial" if remaining else "completed"
            if remaining:
                job.error_message = f"{remaining} eligible full-text documents remain in the import queue. Run another acquisition search to continue."
            job.finished_at = utc_now()
            db.session.commit()
            return _job_payload(job)
        if state.exhausted:
            job.status = "completed"
            job.finished_at = utc_now()
            job.error_message = "This search has reached the end of the available results. Change the search terms to start another search."
            db.session.commit()
            return _job_payload(job)
        items = discover(job.query, min(MAX_RECORDS_PER_RUN, max(1, job.requested_limit)), state)
        state.last_run_at = utc_now()
        db.session.commit()
        job.discovered_count = len(items)
        db.session.commit()
        downloads_remaining = MAX_DOWNLOADS_PER_RUN
        for item in items:
            try:
                record, is_new = _upsert_scholarly_record(item)
                if is_new:
                    job.new_records_count += 1
                else:
                    job.duplicate_count += 1
                db.session.commit()
                record = db.session.get(ScholarlyRecord, record.record_id)
                if record.document_id:
                    continue
                may_probe_xml_license = record.full_text_format == "xml" and record.full_text_url
                if (record.rights_status == "eligible" or may_probe_xml_license) and record.full_text_url:
                    if downloads_remaining > 0:
                        downloads_remaining -= 1
                        result, error = _attempt_full_text(record, job.requested_by_user_id)
                        if result in {"indexed", "already_indexed"}:
                            job.indexed_count += 1
                        elif result == "metadata_only":
                            job.metadata_only_count += 1
                        if error:
                            job.failed_count += 1
                else:
                    job.metadata_only_count += 1
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                job = db.session.get(AcquisitionJob, job_id)
                job.failed_count += 1
                current_app.logger.warning("Acquisition record failed (%s): %s", item.get("provider_id"), exc)
                db.session.commit()

        job = db.session.get(AcquisitionJob, job_id)
        pending_count = _pending_full_text_query().count()
        job.status = "partial" if job.failed_count or pending_count else "completed"
        if pending_count:
            job.error_message = f"{pending_count} eligible full-text documents remain in the import queue. Run another acquisition search to continue."
        job.finished_at = utc_now()
        db.session.commit()
        return _job_payload(job)
    except Exception as exc:
        db.session.rollback()
        job = db.session.get(AcquisitionJob, job_id)
        job.status = "failed"
        job.error_message = str(exc)[:2000]
        job.finished_at = utc_now()
        db.session.commit()
        current_app.logger.exception("Scholarly acquisition job %s failed.", job_id)
        return _job_payload(job)


def create_and_run_job(provider, query, requested_limit, admin_user_id):
    if provider not in DISCOVERY_FUNCTIONS:
        raise ValueError("Select a supported scholarly source.")
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if len(query) < 3 or len(query) > 500:
        raise ValueError("Enter a search query containing between 3 and 500 characters.")
    try:
        requested_limit = int(requested_limit)
    except (TypeError, ValueError):
        requested_limit = 10
    requested_limit = min(MAX_RECORDS_PER_RUN, max(1, requested_limit))
    query_hash = hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()
    state = AcquisitionSearchState.query.filter_by(provider=provider, query_hash=query_hash).first()
    if state is None:
        state = AcquisitionSearchState(
            provider=provider,
            query_hash=query_hash,
            query=query,
            cursor="*" if provider == "openalex" else None,
            offset=0,
            page=1,
            exhausted=False,
        )
        db.session.add(state)
        db.session.flush()
    elif state.exhausted and _pending_full_text_query().count() == 0:
        raise ValueError("This provider has no more results for the saved search. Change the search terms to start a new search.")
    job = AcquisitionJob(
        provider=provider,
        query=query,
        requested_limit=requested_limit,
        status="queued",
        search_state_id=state.state_id,
        requested_by_user_id=admin_user_id,
    )
    db.session.add(job)
    db.session.commit()
    return run_acquisition_job(job.job_id)
