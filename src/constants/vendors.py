from typing import Dict, Set

# ── Vendor-owned shared components (skip only if owner app is installed) ────

MICROSOFT_SUITE_PREFIXES: Set[str] = {
    "com.microsoft.office",
    "com.microsoft.word",
    "com.microsoft.excel",
    "com.microsoft.powerpoint",
    "com.microsoft.outlook",
    "com.microsoft.onenote",
    "com.microsoft.onenote.mac",
    "com.microsoft.teams",
    "com.microsoft.teams2",
    "com.microsoft.onedrive",
    "com.microsoft.edgemac",
}

VENDOR_COMPONENT_OWNERS: Dict[str, Set[str]] = {
    "com.microsoft.office": MICROSOFT_SUITE_PREFIXES,
    "com.microsoft.office.licensing": MICROSOFT_SUITE_PREFIXES,
    "com.microsoft.office.licensingv2": MICROSOFT_SUITE_PREFIXES,
    "com.microsoft.autoupdate": MICROSOFT_SUITE_PREFIXES,
    "com.microsoft.autoupdate2": MICROSOFT_SUITE_PREFIXES,
    "com.microsoft.onedriveupdater": {"com.microsoft.onedrive"},
    "com.microsoft.onedrivestandaloneupdater": {"com.microsoft.onedrive"},
    "com.microsoft.syncreporter": {"com.microsoft.onedrive", "com.microsoft.teams"},
    "com.microsoft.sharepoint": {"com.microsoft.onedrive", "com.microsoft.outlook", "com.microsoft.teams"},
    "com.microsoft.shared": MICROSOFT_SUITE_PREFIXES,
    "com.google.keystone": {"com.google"},
    "com.google.googleupdater": {"com.google"},
    "com.adobe.acc.AdobeCreativeCloud": {"com.adobe"},
    "com.adobe.creativecloud": {"com.adobe"},
}
