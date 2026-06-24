import html
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import quote

import requests
import streamlit as st


st.set_page_config(
    page_title="Hug-The-Tool :: IP Enrichment",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

REQUEST_TIMEOUT = (2.5, 6.0)
INTERNAL_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)

st.markdown(
    """
    <style>
    :root {
        --bg:           #090d18;
        --surface:      #0f1624;
        --border:       rgba(0, 212, 255, 0.1);
        --border-hi:    rgba(0, 212, 255, 0.35);
        --cyan:         #00d4ff;
        --cyan-dim:     rgba(0, 212, 255, 0.5);
        --green:        #00e676;
        --red:          #ff5252;
        --text:         #b8c8d8;
        --text-dim:     #4a6070;
        color-scheme: dark;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes titleGlow {
        0%,100% { box-shadow: 0 0 14px rgba(0,212,255,0.15), inset 0 0 30px rgba(0,212,255,0.03); }
        50%     { box-shadow: 0 0 32px rgba(0,212,255,0.32), inset 0 0 40px rgba(0,212,255,0.07); }
    }
    @keyframes shimmer {
        0%   { background-position: -200% center; }
        100% { background-position:  200% center; }
    }
    @keyframes scanPulse {
        0%,100% { opacity: 0.5; }
        50%     { opacity: 1; }
    }
    @keyframes cardBorderFlash {
        0%,100% { border-top-color: rgba(0,212,255,0.18); }
        50%     { border-top-color: rgba(0,212,255,0.55); }
    }

    html, body, [data-testid="stAppViewContainer"], .stApp {
        height: 100vh;
        overflow: hidden;
        background-color: var(--bg);
        background-image:
            linear-gradient(rgba(0,212,255,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,212,255,0.025) 1px, transparent 1px);
        background-size: 44px 44px;
        background-attachment: fixed;
        color: var(--text);
        font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"], footer {
        display: none !important;
    }
    .block-container {
        max-width: 1500px;
        height: 100vh;
        padding: 0.55rem 1rem 0.35rem !important;
    }
    h1, h2, h3, p { margin: 0; }

    /* ── Title ── */
    .retro-title {
        background: linear-gradient(135deg, #0d1b2e 0%, #09111f 100%);
        border: 1px solid var(--border-hi);
        border-left: 3px solid var(--cyan);
        color: var(--cyan);
        font: bold 17px "Courier New", monospace;
        letter-spacing: 4px;
        padding: 10px 16px;
        text-transform: uppercase;
        position: relative;
        overflow: hidden;
        animation: titleGlow 4s ease-in-out infinite;
    }
    .retro-title::after {
        content: '';
        position: absolute;
        left: 0; right: 0; bottom: 0; height: 1px;
        background: linear-gradient(90deg, transparent 0%, var(--cyan) 50%, transparent 100%);
        background-size: 200% 100%;
        animation: shimmer 3s linear infinite;
    }

    /* ── Subtitle ── */
    .retro-subtitle {
        background: transparent;
        border: none;
        border-left: 2px solid var(--border-hi);
        color: var(--text-dim);
        font: 10px "Courier New", monospace;
        letter-spacing: 2px;
        padding: 3px 10px;
        margin-bottom: 5px;
    }

    /* ── Form ── */
    [data-testid="stForm"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: 2px solid rgba(0,212,255,0.15);
        padding: 8px 10px 4px;
    }
    [data-testid="stTextInput"] label {
        color: var(--cyan) !important;
        font: bold 10px "Courier New", monospace !important;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    [data-testid="stTextInput"] input {
        height: 36px;
        background: #050810 !important;
        border: 1px solid rgba(0,212,255,0.2) !important;
        border-radius: 1px !important;
        color: var(--cyan) !important;
        font: 14px "Courier New", monospace !important;
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: var(--cyan) !important;
        box-shadow: 0 0 0 1px rgba(0,212,255,0.15), 0 0 14px rgba(0,212,255,0.1) !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] input::placeholder {
        color: var(--text-dim) !important;
    }

    /* ── Checkboxes ── */
    [data-testid="stCheckbox"] { min-height: 25px; }
    [data-testid="stCheckbox"] label {
        color: var(--text-dim) !important;
        font: 10px "Courier New", monospace !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        transition: color 0.2s;
    }
    [data-testid="stCheckbox"] label p { color: var(--text-dim) !important; }
    [data-testid="stCheckbox"] label:has(input:checked) { color: var(--cyan) !important; }
    [data-testid="stCheckbox"] label:has(input:checked) p { color: var(--cyan) !important; }
    [data-testid="stCheckbox"] label:has(input:checked) > span {
        background-color: var(--cyan) !important;
        border-color: var(--cyan) !important;
    }
    [data-testid="stCheckbox"] label:has(input:focus-visible) > span {
        box-shadow: 0 0 0 2px rgba(0,212,255,0.35) !important;
    }

    /* ── Button ── */
    .stButton > button, [data-testid="stFormSubmitButton"] button {
        min-height: 36px;
        border: 1px solid var(--border-hi) !important;
        border-radius: 2px !important;
        background: rgba(0,212,255,0.06) !important;
        color: var(--cyan) !important;
        font: bold 11px "Courier New", monospace !important;
        letter-spacing: 2px;
        text-transform: uppercase;
        transition: background 0.25s, box-shadow 0.25s;
    }
    .stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
        background: rgba(0,212,255,0.14) !important;
        box-shadow: 0 0 18px rgba(0,212,255,0.25) !important;
    }
    .stButton > button:active, [data-testid="stFormSubmitButton"] button:active {
        background: rgba(0,212,255,0.22) !important;
    }

    /* ── Section label ── */
    .section-label {
        background: transparent;
        border-bottom: 1px solid var(--border);
        border-left: 2px solid var(--cyan);
        color: var(--cyan);
        font: bold 10px "Courier New", monospace;
        letter-spacing: 3px;
        padding: 4px 10px;
        margin: 6px 0;
        text-transform: uppercase;
    }

    /* ── Source cards ── */
    .source-card {
        min-height: 91px;
        background: var(--surface);
        border: 1px solid var(--border);
        border-top: 2px solid rgba(0,212,255,0.18);
        color: var(--text);
        font: 11px "Courier New", monospace;
        line-height: 1.55;
        padding: 0 8px 6px;
        margin-bottom: 6px;
        position: relative;
        overflow: hidden;
        transition: border-color 0.25s, box-shadow 0.25s, transform 0.2s;
        animation: fadeInUp 0.4s ease both;
    }
    .source-card::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(0,212,255,0.03) 0%, transparent 55%);
        pointer-events: none;
    }
    .source-card:hover {
        border-color: rgba(0,212,255,0.4);
        border-top-color: var(--cyan);
        box-shadow: 0 4px 24px rgba(0,212,255,0.09);
        transform: translateY(-2px);
    }
    /* stagger card entrance per column */
    [data-testid="column"]:nth-child(1) .source-card { animation-delay:   0ms; }
    [data-testid="column"]:nth-child(2) .source-card { animation-delay:  70ms; }
    [data-testid="column"]:nth-child(3) .source-card { animation-delay: 140ms; }
    [data-testid="column"]:nth-child(4) .source-card { animation-delay: 210ms; }

    .source-card b { color: var(--text-dim); font-weight: normal; }

    /* ── Card title bar ── */
    .source-title {
        background: linear-gradient(90deg, rgba(0,212,255,0.1) 0%, transparent 80%);
        border-bottom: 1px solid var(--border);
        border-left: 2px solid var(--cyan);
        color: var(--cyan);
        font: bold 9px "Courier New", monospace;
        letter-spacing: 2px;
        margin: 0 -8px 6px;
        padding: 4px 8px;
        text-transform: uppercase;
    }

    /* ── Status badges ── */
    .ok   { color: var(--green); font-weight: bold; letter-spacing: 0.5px; }
    .bad  { color: var(--red);   font-weight: bold; letter-spacing: 0.5px; }
    .skip { color: var(--text-dim); }

    /* ── Pivot link ── */
    .pivot-link {
        float: right;
        color: var(--cyan-dim);
        font: 9px "Courier New", monospace;
        text-decoration: none;
        letter-spacing: 1px;
        border: 1px solid rgba(0,212,255,0.2);
        padding: 1px 5px;
        transition: color 0.2s, border-color 0.2s, box-shadow 0.2s;
    }
    .pivot-link:hover {
        color: var(--cyan);
        border-color: var(--cyan);
        box-shadow: 0 0 8px rgba(0,212,255,0.2);
    }
    .pivot-link:visited { color: rgba(140,90,210,0.6); }

    /* ── Code block ── */
    [data-testid="stCodeBlock"] {
        border: 1px solid var(--border);
        border-radius: 2px;
    }
    [data-testid="stCodeBlock"] pre {
        max-height: 275px;
        font-size: 11px;
        background: #050810 !important;
    }
    [data-testid="stCode"] [data-testid="stElementToolbarButton"],
    [data-testid="stCode"] [data-testid="stTooltipHoverTarget"] {
        opacity: 1 !important;
        visibility: visible !important;
    }
    [data-testid="stCode"] [data-testid="stBaseButton-elementToolbar"] {
        width: auto !important;
        min-height: 26px !important;
        padding: 2px 8px !important;
        background: rgba(0,212,255,0.08) !important;
        border: 1px solid rgba(0,212,255,0.25) !important;
        border-radius: 2px !important;
        color: var(--cyan) !important;
        font: bold 9px "Courier New", monospace !important;
        letter-spacing: 1px !important;
    }
    [data-testid="stCode"] [data-testid="stBaseButton-elementToolbar"]::after {
        content: " COPY TO CLIPBOARD";
    }

    /* ── Alerts ── */
    [data-testid="stAlert"] {
        border-radius: 2px;
        padding: 6px 12px;
        font: bold 11px "Courier New", monospace;
        letter-spacing: 1px;
        background: var(--surface) !important;
    }

    /* ── Spinner ── */
    [data-testid="stSpinner"] {
        font: bold 11px "Courier New", monospace;
        color: var(--cyan) !important;
        letter-spacing: 2px;
        animation: scanPulse 1.2s ease-in-out infinite;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def secret(name: str) -> str | None:
    """Read API credentials only from Streamlit's secret store."""
    try:
        value = st.secrets[name]
    except (KeyError, FileNotFoundError):
        return None
    return str(value).strip() or None


def is_internal(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Block internal and other non-routable targets before any network call."""
    return (
        any(ip_obj in network for network in INTERNAL_NETWORKS)
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_unspecified
        or ip_obj.is_multicast
        or ip_obj.is_reserved
    )


def unavailable(reason: str) -> dict[str, Any]:
    return {"ok": False, "data": {}, "reason": reason}


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 429:
            return unavailable("Rate Limited")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return unavailable("Invalid Response")
        return {"ok": True, "data": payload, "reason": ""}
    except requests.Timeout:
        return unavailable("Timed Out")
    except (requests.RequestException, ValueError):
        return unavailable("Request Failed")


def query_virustotal(ip: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return unavailable("API Key Missing")
    return request_json(
        f"https://www.virustotal.com/api/v3/ip_addresses/{quote(ip, safe='')}",
        headers={"x-apikey": api_key, "Accept": "application/json"},
    )


def query_abuseipdb(ip: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return unavailable("API Key Missing")
    result = request_json(
        "https://api.abuseipdb.com/api/v2/check",
        headers={"Key": api_key, "Accept": "application/json"},
        params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""},
    )
    if result["ok"]:
        data = result["data"].get("data")
        if not isinstance(data, dict):
            return unavailable("Invalid Response")
        result["data"] = data
    return result


def query_otx(ip: str, version: int, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return unavailable("API Key Missing")
    indicator_type = "IPv4" if version == 4 else "IPv6"
    return request_json(
        f"https://otx.alienvault.com/api/v1/indicators/{indicator_type}/{quote(ip, safe='')}/general",
        headers={"X-OTX-API-KEY": api_key, "Accept": "application/json"},
    )


def query_vpnapi(ip: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return unavailable("API Key Missing")
    return request_json(
        f"https://vpnapi.io/api/{quote(ip, safe='')}",
        params={"key": api_key},
        headers={"Accept": "application/json"},
    )


def query_ipinfo(ip: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return unavailable("API Key Missing")
    return request_json(
        f"https://ipinfo.io/{quote(ip, safe='')}/json",
        params={"token": api_key},
        headers={"Accept": "application/json"},
    )


def query_ipapi_is(ip: str, api_key: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {"q": ip}
    if api_key:
        params["key"] = api_key
    return request_json(
        "https://api.ipapi.is",
        params=params,
        headers={"Accept": "application/json"},
    )


@st.cache_data(ttl=300, max_entries=256, show_spinner=False)
def run_enrichment(
    ip: str,
    ip_version: int,
    selected_apis: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    all_jobs = {
        "vt": lambda: (query_virustotal, (ip, secret("VT_API_KEY"))),
        "abuse": lambda: (query_abuseipdb, (ip, secret("ABUSE_API_KEY"))),
        "otx": lambda: (query_otx, (ip, ip_version, secret("OTX_API_KEY"))),
        "vpn": lambda: (query_vpnapi, (ip, secret("VPNAPI_KEY"))),
        "ipinfo": lambda: (query_ipinfo, (ip, secret("IPINFO_TOKEN"))),
        "ipapiis": lambda: (query_ipapi_is, (ip, secret("IPAPI_IS_KEY"))),
    }
    jobs = {name: all_jobs[name]() for name in selected_apis}
    results = {
        name: unavailable("Not Selected")
        for name in all_jobs
        if name not in selected_apis
    }
    if not jobs:
        return results
    with ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="enrichment") as pool:
        futures = {
            pool.submit(function, *arguments): name
            for name, (function, arguments) in jobs.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = unavailable("Data Unavailable")
    return results


def value(data: dict[str, Any], key: str, default: Any = "Data Unavailable") -> Any:
    if not isinstance(data, dict):
        return default
    found = data.get(key, default)
    return default if found is None or found == "" else found


def safe_text(raw: Any) -> str:
    return html.escape(str(raw))


def status_text(result: dict[str, Any]) -> str:
    if result["ok"]:
        return '<span class="ok">AVAILABLE</span>'
    if result["reason"] == "Not Selected":
        return '<span class="skip">NOT SELECTED</span>'
    if result["reason"] == "Manual Check":
        return '<span class="skip">MANUAL CHECK</span>'
    return f'<span class="bad">Data Unavailable ({safe_text(result["reason"])})</span>'


SPUR_MANUAL: dict[str, Any] = {"ok": False, "data": {}, "reason": "Manual Check"}


def source_card(
    title: str,
    result: dict[str, Any],
    lines: list[tuple[str, Any]],
    pivot_url: str,
) -> str:
    if result["reason"] == "Not Selected":
        details = "Skipped by analyst"
    else:
        details = "<br>".join(
            f"<b>{safe_text(label)}:</b> {safe_text(raw_value)}"
            for label, raw_value in lines
        )
    return (
        '<div class="source-card">'
        f'<div class="source-title">{safe_text(title)}</div>'
        f"{status_text(result)}"
        f'<a class="pivot-link" href="{html.escape(pivot_url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">[OPEN WEB]</a>'
        f"<br>{details}"
        "</div>"
    )


def investigation_export(payload: dict[str, Any]) -> str:
    """Create a clean analyst-ready export containing only useful values."""
    unavailable_values = {"", "data unavailable", "unknown", "n/a", "none", "null"}
    relevant_lines = ["Intelligence:"]
    for field, raw_value in payload.items():
        if raw_value is None:
            continue
        if isinstance(raw_value, str) and raw_value.strip().lower() in unavailable_values:
            continue
        relevant_lines.append(f"{field}: {raw_value}")
    return "\n".join(relevant_lines)


st.markdown('<div class="retro-title">HUG-THE-TOOL :: IP ENRICHMENT CONSOLE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="retro-subtitle">It doesn&#39;t bite.</div>',
    unsafe_allow_html=True,
)

with st.form("ip_lookup", clear_on_submit=False):
    input_column, button_column = st.columns([6, 1], vertical_alignment="bottom")
    with input_column:
        ip_input = st.text_input(
            "TARGET IPv4 / IPv6 ADDRESS",
            placeholder="8.8.8.8",
            autocomplete="off",
            label_visibility="visible",
        )
    with button_column:
        submitted = st.form_submit_button("RUN TRIAGE", use_container_width=True)
    abuse_column, vt_column, otx_column, vpn_column, ipapiis_column, ipinfo_column = st.columns(6)
    with abuse_column:
        use_abuse = st.checkbox("AbuseIPDB", value=True)
    with vt_column:
        use_vt = st.checkbox("VirusTotal", value=False)
    with otx_column:
        use_otx = st.checkbox("AlienVault OTX", value=False)
    with vpn_column:
        use_vpn = st.checkbox("VPNAPI.io", value=False)
    with ipapiis_column:
        use_ipapiis = st.checkbox("ipapi.is", value=False)
    with ipinfo_column:
        use_ipinfo = st.checkbox("IPInfo.io", value=False)

if not submitted:
    st.markdown(
        """
        <div class="source-card" style="min-height:120px; margin-top:8px;">
          <div class="source-title">SYSTEM READY</div>
          Enter one public IPv4 or IPv6 address and select RUN TRIAGE.<br><br>
          Internal and non-routable addresses are rejected locally before any API request.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

selected_apis = tuple(
    name
    for name, enabled in (
        ("vt", use_vt),
        ("abuse", use_abuse),
        ("otx", use_otx),
        ("vpn", use_vpn),
        ("ipinfo", use_ipinfo),
        ("ipapiis", use_ipapiis),
    )
    if enabled
)
if not selected_apis:
    st.warning("Select at least one API")
    st.stop()

candidate = ip_input.strip()
try:
    ip_object = ipaddress.ip_address(candidate)
except ValueError:
    st.error("Invalid IP address")
    st.stop()

if is_internal(ip_object):
    st.error("Internal IP detected")
    st.stop()

ip_address = str(ip_object)
selected_names = {
    "vt": "VT",
    "abuse": "ABUSEIPDB",
    "otx": "OTX",
    "vpn": "VPNAPI",
    "ipinfo": "IPINFO",
    "ipapiis": "IPAPI.IS",
}
spinner_sources = " / ".join(
    selected_names[name] for name in ("vt", "abuse", "otx", "vpn", "ipinfo", "ipapiis") if name in selected_apis
)
with st.spinner(f"CONTACTING {spinner_sources} ..."):
    api_results = run_enrichment(ip_address, ip_object.version, selected_apis)

encoded_ip = quote(ip_address, safe="")
pivot_urls = {
    "vt": f"https://www.virustotal.com/gui/ip-address/{encoded_ip}",
    "abuse": f"https://www.abuseipdb.com/check/{encoded_ip}",
    "otx": f"https://otx.alienvault.com/indicator/ip/{encoded_ip}",
    "vpn": "https://vpnapi.io/vpn-detection",
    "ipinfo": f"https://ipinfo.io/{encoded_ip}",
    "spur": f"https://spur.us/context/{encoded_ip}",
    "ipapiis": f"https://ipapi.is/?q={encoded_ip}",
}

vt_result = api_results["vt"]
abuse_result = api_results["abuse"]
otx_result = api_results["otx"]
vpn_result = api_results["vpn"]
ipinfo_result = api_results["ipinfo"]
ipapiis_result = api_results["ipapiis"]

vt_data = vt_result["data"].get("data", {}) if vt_result["ok"] else {}
vt_attributes = vt_data.get("attributes", {}) if isinstance(vt_data, dict) else {}
vt_stats = vt_attributes.get("last_analysis_stats", {}) if isinstance(vt_attributes, dict) else {}
otx_pulse_info = otx_result["data"].get("pulse_info", {}) if otx_result["ok"] else {}
otx_pulses = value(otx_pulse_info, "count")
otx_reputation = value(otx_result["data"], "reputation") if otx_result["ok"] else "Data Unavailable"
vpn_security = vpn_result["data"].get("security", {}) if vpn_result["ok"] else {}
if not isinstance(vpn_security, dict):
    vpn_security = {}
ipinfo_data = ipinfo_result["data"] if ipinfo_result["ok"] else {}
ipinfo_privacy = ipinfo_data.get("privacy", {}) if isinstance(ipinfo_data, dict) else {}
if not isinstance(ipinfo_privacy, dict):
    ipinfo_privacy = {}
ipapiis_data = ipapiis_result["data"] if ipapiis_result["ok"] else {}

if abuse_result["ok"]:
    abuse = dict(abuse_result["data"])
    abuse["lastReportedAt"] = str(abuse.get("lastReportedAt") or "N/A")
else:
    abuse = {
        "abuseConfidenceScore": "Data Unavailable",
        "isp": "Data Unavailable",
        "countryName": "Data Unavailable",
        "totalReports": "Data Unavailable",
        "lastReportedAt": "Data Unavailable",
        "domain": "Data Unavailable",
    }

vpnapi_says_vpn: bool | None = None
if vpn_result["ok"] and isinstance(vpn_security, dict):
    raw = vpn_security.get("vpn")
    if raw is not None:
        vpnapi_says_vpn = bool(raw)

ipinfo_says_vpn: bool | None = None
if ipinfo_result["ok"] and ipinfo_privacy:
    raw = ipinfo_privacy.get("vpn")
    if raw is not None:
        ipinfo_says_vpn = bool(raw)

ipapiis_says_vpn: bool | None = None
if ipapiis_result["ok"] and isinstance(ipapiis_data, dict):
    raw = ipapiis_data.get("is_vpn")
    if raw is not None:
        ipapiis_says_vpn = bool(raw)

_vpn_opinions = [v for v in (vpnapi_says_vpn, ipinfo_says_vpn, ipapiis_says_vpn) if v is not None]
if not _vpn_opinions:
    vpn_consensus: bool | str = "Data Unavailable"
elif len(_vpn_opinions) == 1:
    vpn_consensus = _vpn_opinions[0]
else:
    _true = sum(1 for v in _vpn_opinions if v)
    _false = len(_vpn_opinions) - _true
    vpn_consensus = "Conflicting Sources" if _true == _false else _true > _false

score = abuse.get("abuseConfidenceScore", "Data Unavailable")
score_display = f"{score}%" if isinstance(score, (int, float)) else score
provider = abuse.get("isp", "Data Unavailable")

payload = {
    "IP Address": ip_address,
    "Abuse Score": score_display,
    "ISP / Provider": provider,
    "Country": abuse.get("countryName", "Unknown"),
    "Total Reports": abuse.get("totalReports", 0),
    "Last Reported": (
        abuse.get("lastReportedAt", "N/A")[:10]
        if abuse_result["ok"]
        else "Data Unavailable"
    ),
    "Domain": abuse.get("domain", "N/A"),
    "VPN": vpn_consensus,
}

sources_column, export_column = st.columns([1.15, 0.85], gap="small")
with sources_column:
    st.markdown('<div class="section-label">SOURCE TRIAGE</div>', unsafe_allow_html=True)
    r1c1, r1c2, r1c3 = st.columns(3, gap="small")
    r2c1, r2c2, r2c3, r2c4 = st.columns(4, gap="small")
    with r1c1:
        st.markdown(
            source_card(
                "ABUSEIPDB v2",
                abuse_result,
                [
                    ("Abuse Score", score_display),
                    ("Total Reports", abuse.get("totalReports", "Data Unavailable")),
                    ("ISP", provider),
                ],
                pivot_urls["abuse"],
            ),
            unsafe_allow_html=True,
        )
    with r1c2:
        st.markdown(
            source_card(
                "VIRUSTOTAL v3",
                vt_result,
                [
                    ("Malicious", value(vt_stats, "malicious")),
                    ("Suspicious", value(vt_stats, "suspicious")),
                    ("AS Owner", value(vt_attributes, "as_owner")),
                ],
                pivot_urls["vt"],
            ),
            unsafe_allow_html=True,
        )
    with r1c3:
        st.markdown(
            source_card(
                "ALIENVAULT OTX",
                otx_result,
                [
                    ("Pulse Count", otx_pulses),
                    ("Reputation", otx_reputation),
                    ("Indicator", ip_address),
                ],
                pivot_urls["otx"],
            ),
            unsafe_allow_html=True,
        )
    with r2c1:
        st.markdown(
            source_card(
                "VPNAPI.io",
                vpn_result,
                [
                    ("VPN", value(vpn_security, "vpn")),
                    ("Proxy", value(vpn_security, "proxy")),
                    ("TOR", value(vpn_security, "tor")),
                ],
                pivot_urls["vpn"],
            ),
            unsafe_allow_html=True,
        )
    with r2c2:
        st.markdown(
            source_card(
                "IPAPI.IS",
                ipapiis_result,
                [
                    ("VPN", value(ipapiis_data, "is_vpn")),
                    ("Proxy", value(ipapiis_data, "is_proxy")),
                    ("TOR", value(ipapiis_data, "is_tor")),
                ],
                pivot_urls["ipapiis"],
            ),
            unsafe_allow_html=True,
        )
    with r2c3:
        st.markdown(
            source_card(
                "IPINFO.io",
                ipinfo_result,
                [
                    ("Org", value(ipinfo_data, "org")),
                    ("Country", value(ipinfo_data, "country")),
                    ("VPN", "Manual — open web link"),
                ],
                pivot_urls["ipinfo"],
            ),
            unsafe_allow_html=True,
        )
    with r2c4:
        st.markdown(
            source_card(
                "SPUR.US",
                SPUR_MANUAL,
                [("VPN", "Manual — open web link")],
                pivot_urls["spur"],
            ),
            unsafe_allow_html=True,
        )

with export_column:
    st.markdown('<div class="section-label">CONSOLIDATED EXPORT</div>', unsafe_allow_html=True)
    export_text = investigation_export(payload)
    st.code(export_text, language=None, line_numbers=False)
