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
        color-scheme: light;
    }
    html, body, [data-testid="stAppViewContainer"], .stApp {
        height: 100vh;
        overflow: hidden;
        background: #c0c0c0;
        color: #000080;
        font-family: Verdana, Arial, sans-serif;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"], footer {
        display: none !important;
    }
    .block-container {
        max-width: 1500px;
        height: 100vh;
        padding: 0.55rem 1rem 0.35rem !important;
    }
    h1, h2, h3, p {
        margin: 0;
    }
    .retro-title {
        background: #000080;
        color: #ffff00;
        border: 3px outset #dfdfdf;
        font: bold 20px "Courier New", monospace;
        letter-spacing: 1px;
        padding: 7px 12px;
        text-shadow: 1px 1px #000;
    }
    .retro-subtitle {
        background: #ffffcc;
        border: 2px inset #fff;
        color: #000;
        font: 11px Verdana, sans-serif;
        padding: 3px 8px;
        margin-bottom: 5px;
    }
    [data-testid="stForm"] {
        background: #d4d0c8;
        border: 2px outset #fff;
        padding: 5px 8px 1px;
    }
    [data-testid="stTextInput"] label {
        color: #000;
        font: bold 11px Verdana, sans-serif;
    }
    [data-testid="stTextInput"] input {
        height: 34px;
        background: #fff;
        border: 2px inset #fff;
        border-radius: 0;
        color: #000;
        font: 14px "Courier New", monospace;
    }
    [data-testid="stCheckbox"] {
        min-height: 25px;
    }
    [data-testid="stCheckbox"] label {
        color: #000;
        font: bold 11px Verdana, sans-serif;
    }
    .stButton > button, [data-testid="stFormSubmitButton"] button {
        min-height: 34px;
        border: 2px outset #fff;
        border-radius: 0;
        background: #d4d0c8;
        color: #000;
        font: bold 12px Verdana, sans-serif;
    }
    .stButton > button:active, [data-testid="stFormSubmitButton"] button:active {
        border-style: inset;
    }
    .section-label {
        background: #808080;
        border: 2px outset #fff;
        color: #fff;
        font: bold 12px Verdana, sans-serif;
        padding: 3px 7px;
        margin: 4px 0;
    }
    .source-card {
        min-height: 91px;
        background: #f0f0e8;
        border: 2px outset #fff;
        color: #000;
        font: 11px Verdana, sans-serif;
        line-height: 1.45;
        padding: 5px 7px;
        margin-bottom: 5px;
    }
    .source-card b {
        color: #000080;
    }
    .source-title {
        background: #000080;
        color: #fff;
        font: bold 11px "Courier New", monospace;
        margin: -5px -7px 4px;
        padding: 2px 5px;
    }
    .ok {
        color: #006400;
        font-weight: bold;
    }
    .bad {
        color: #a00000;
        font-weight: bold;
    }
    .skip {
        color: #505050;
        font-weight: bold;
    }
    [data-testid="stCodeBlock"] {
        border: 2px inset #fff;
        border-radius: 0;
    }
    [data-testid="stCodeBlock"] pre {
        max-height: 275px;
        font-size: 11px;
    }
    [data-testid="stCode"] [data-testid="stElementToolbarButton"],
    [data-testid="stCode"] [data-testid="stTooltipHoverTarget"] {
        opacity: 1 !important;
        visibility: visible !important;
    }
    [data-testid="stCode"] [data-testid="stBaseButton-elementToolbar"] {
        width: auto !important;
        min-height: 28px !important;
        padding: 2px 6px !important;
        background: #d4d0c8 !important;
        border: 2px outset #fff !important;
        border-radius: 0 !important;
        color: #000 !important;
        font: bold 10px Verdana, sans-serif !important;
    }
    [data-testid="stCode"] [data-testid="stBaseButton-elementToolbar"]::after {
        content: " COPY TO CLIPBOARD";
    }
    [data-testid="stAlert"] {
        border-radius: 0;
        border: 2px outset #fff;
        padding: 6px 10px;
        font: bold 12px Verdana, sans-serif;
    }
    [data-testid="stSpinner"] {
        font: bold 12px "Courier New", monospace;
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


def run_enrichment(
    ip: str,
    ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address,
    selected_apis: set[str],
) -> dict[str, dict[str, Any]]:
    all_jobs = {
        "vt": lambda: (query_virustotal, (ip, secret("VT_API_KEY"))),
        "abuse": lambda: (query_abuseipdb, (ip, secret("ABUSE_API_KEY"))),
        "otx": lambda: (query_otx, (ip, ip_obj.version, secret("OTX_API_KEY"))),
        "vpn": lambda: (query_vpnapi, (ip, secret("VPNAPI_KEY"))),
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
    return f'<span class="bad">Data Unavailable ({safe_text(result["reason"])})</span>'


def source_card(title: str, result: dict[str, Any], lines: list[tuple[str, Any]]) -> str:
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
        f"{status_text(result)}<br>{details}"
        "</div>"
    )


def investigation_export(payload: dict[str, Any]) -> str:
    """Create a clean analyst-ready export containing only useful values."""
    unavailable_values = {"", "data unavailable", "unknown", "n/a", "none", "null"}
    relevant_lines = []
    for field, raw_value in payload.items():
        if raw_value is None:
            continue
        if isinstance(raw_value, str) and raw_value.strip().lower() in unavailable_values:
            continue
        relevant_lines.append(f"{field}: {raw_value}")
    return "\n".join(relevant_lines)


st.markdown('<div class="retro-title">HUG-THE-TOOL :: IP ENRICHMENT CONSOLE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="retro-subtitle">Four-source OSINT triage / no query logging, caching, or persistence</div>',
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
    vt_column, abuse_column, otx_column, vpn_column = st.columns(4)
    with vt_column:
        use_vt = st.checkbox("VirusTotal", value=False)
    with abuse_column:
        use_abuse = st.checkbox("AbuseIPDB", value=True)
    with otx_column:
        use_otx = st.checkbox("AlienVault OTX", value=True)
    with vpn_column:
        use_vpn = st.checkbox("VPNAPI.io", value=True)

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

selected_apis = {
    name
    for name, enabled in {
        "vt": use_vt,
        "abuse": use_abuse,
        "otx": use_otx,
        "vpn": use_vpn,
    }.items()
    if enabled
}
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
}
spinner_sources = " / ".join(
    selected_names[name] for name in ("vt", "abuse", "otx", "vpn") if name in selected_apis
)
with st.spinner(f"CONTACTING {spinner_sources} ..."):
    api_results = run_enrichment(ip_address, ip_object, selected_apis)

vt_result = api_results["vt"]
abuse_result = api_results["abuse"]
otx_result = api_results["otx"]
vpn_result = api_results["vpn"]

vt_data = vt_result["data"].get("data", {}) if vt_result["ok"] else {}
vt_attributes = vt_data.get("attributes", {}) if isinstance(vt_data, dict) else {}
vt_stats = vt_attributes.get("last_analysis_stats", {}) if isinstance(vt_attributes, dict) else {}
otx_pulse_info = otx_result["data"].get("pulse_info", {}) if otx_result["ok"] else {}
otx_pulses = value(otx_pulse_info, "count")
otx_reputation = value(otx_result["data"], "reputation") if otx_result["ok"] else "Data Unavailable"
vpn_security = vpn_result["data"].get("security", {}) if vpn_result["ok"] else {}
if not isinstance(vpn_security, dict):
    vpn_security = {}

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

vpn = (
    {"vpn": value(vpn_security, "vpn", False)}
    if vpn_result["ok"] and isinstance(vpn_security, dict)
    else {"vpn": "Data Unavailable"}
)
score = abuse.get("abuseConfidenceScore", "Data Unavailable")
provider = abuse.get("isp", "Data Unavailable")

payload = {
    "IP Address": ip_address,
    "Abuse Score": score,
    "ISP / Provider": provider,
    "Country": abuse.get("countryName", "Unknown"),
    "Total Reports": abuse.get("totalReports", 0),
    "Last Reported": (
        abuse.get("lastReportedAt", "N/A")[:10]
        if abuse_result["ok"]
        else "Data Unavailable"
    ),
    "Domain": abuse.get("domain", "N/A"),
    "VPN": vpn.get("vpn", False),
}

sources_column, export_column = st.columns([1.15, 0.85], gap="small")
with sources_column:
    st.markdown('<div class="section-label">SOURCE TRIAGE</div>', unsafe_allow_html=True)
    top_left, top_right = st.columns(2, gap="small")
    bottom_left, bottom_right = st.columns(2, gap="small")
    with top_left:
        st.markdown(
            source_card(
                "VIRUSTOTAL v3",
                vt_result,
                [
                    ("Malicious", value(vt_stats, "malicious")),
                    ("Suspicious", value(vt_stats, "suspicious")),
                    ("AS Owner", value(vt_attributes, "as_owner")),
                ],
            ),
            unsafe_allow_html=True,
        )
    with top_right:
        st.markdown(
            source_card(
                "ABUSEIPDB v2",
                abuse_result,
                [
                    ("Abuse Score", score),
                    ("Total Reports", abuse.get("totalReports", "Data Unavailable")),
                    ("ISP", provider),
                ],
            ),
            unsafe_allow_html=True,
        )
    with bottom_left:
        st.markdown(
            source_card(
                "ALIENVAULT OTX",
                otx_result,
                [
                    ("Pulse Count", otx_pulses),
                    ("Reputation", otx_reputation),
                    ("Indicator", ip_address),
                ],
            ),
            unsafe_allow_html=True,
        )
    with bottom_right:
        st.markdown(
            source_card(
                "VPNAPI.io",
                vpn_result,
                [
                    ("VPN", value(vpn_security, "vpn")),
                    ("Proxy", value(vpn_security, "proxy")),
                    ("TOR", value(vpn_security, "tor")),
                ],
            ),
            unsafe_allow_html=True,
        )

with export_column:
    st.markdown('<div class="section-label">CONSOLIDATED EXPORT</div>', unsafe_allow_html=True)
    export_text = investigation_export(payload)
    st.code(export_text, language=None, line_numbers=False)
