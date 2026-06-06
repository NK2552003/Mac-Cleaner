from typing import Set

# ── System-owned Group Container prefixes (always skip) ───────────────────────

SYSTEM_GROUP_PREFIXES: Set[str] = {
    "group.com.apple.",
    "group.apple.",
    "group.is.workflow.",
    "group.net.ia.",
    "group.tvappservices.",
    "group.com.facebook.",
    "group.com.aviorrok.",
    "group.systempreferences.",
    "group.icloud.",
}

# ── Keyword safelist — any stem starting with these is system-owned ──────────

SYSTEM_KEYWORD_SAFELIST: Set[str] = {
    # Apple core
    "com.apple", "apple", "webkit", "safari", "siri", "spotlight",
    "dock", "finder", "itunes", "music", "photos", "mail", "messages",
    "facetime", "maps", "notes", "reminders", "calendar", "contacts",
    "icloud", "mobiledevice", "systempreferences", "systemsettings",
    "system preferences", "system settings",
    # CoreFrameworks
    "coreaudio", "corevideo", "coredata", "coreservices", "coregraphics",
    "coremedia", "corebluetooth", "corelocation", "coretext", "coreml",
    "coremotion", "coreimage", "corespotlight", "corenfc",
    # Networking daemons
    "networkextension", "security", "screensaver", "scripteditor",
    "voiceover", "accessibility", "loginwindow", "installer",
    "softwareupdate", "appstore", "xpc", "launchd", "mdmclient",
    "cloudd", "nsurlsessiond", "sharingd", "bluetoothd", "wifid",
    "kernelmanagerd", "osanalyticshelper", "analyticsd", "swcd",
    "trustd", "accountsd", "coreduetd", "symptomsd", "mediaremoted",
    "homekitd", "findmydeviced", "duetexpertcenterd", "ctkd",
    # Dev tools (system-bundled)
    "homebrew", "git", "node", "ruby", "python", "pip", "cargo",
    "java", "openjdk", "llvm", "clang", "docker", "kubectl",
    # CUPS / printing
    "cups", "org.cups",
    # Crash / diagnostics
    "crashreporter", "diagnosticreports", "savedapplicationstate",
    "containermanagerd", "addressbook", "dataaccessd",
    # macOS Ventura+ additions
    "tipsd", "translationd", "weatherd", "lockdownmode",
    "passbookd", "healthkitd", "fitnessserviced",
    "screentime", "familycontrols", "devicemanagement",
}

# ── Exact-stem safelist — the stem (lowercased) matches exactly ───────────────

SYSTEM_EXACT_SAFELIST: Set[str] = {
    # ── original entries (verbatim) ────────────────────────────────────
    "systemconfiguration", "opendirectory", "directoryservice",
    "networkserviceproxy", "byhost",
    "askpermissiond", "mbuseragent", "contextstoreagent",
    "sharedfilelistd", "scopedbookmarkagent", "tokenbucketratelimiter",
    "pbs", "mobilemeaccounts", "sesstorage",
    "familycircled", "familycircle",
    "gamekit", "passkit", "healthkit",
    "animoji", "icdd", "callhistorytransactions", "callhistorydb",
    "locationaccessstored", "differentialprivacy",
    "privacypreservingmeasurement", "homeenergyd",
    "btserver", "ilifemediabrowser", "printers",
    "windowserver", "xsan", "hidfw-crashlogs", "hidfw crashlogs",
    "mcxtools", "discrecording",
    "databases",
    "mozilla",
    "proapps",
    "livefsd",
    "knowledge",
    "desktop pictures",
    "baseband",
    "typescript",
    "jna",
    "geoservices",
    "geod",
    "cups",
    "org.cups",
    "cloudkit",
    "cloudkitd",
    "keychain",
    "keychainaccess",
    "securityagent",
    "fontregistry",
    "atsserver",
    "fontd",
    "usernoted",
    "notificationcenter",
    "sandboxd",
    "secinitd",
    "metalpipeline",
    "gpudriver",
    "timemachine",
    "backupd",
    "metadata",
    "mds",
    "mdworker",
    "quicklook",
    "qlgenerator",
    "inputmethod",
    "dictation",
    "powerd",
    "thermald",
    "pmset",
    "assistant",
    "assistantd",
    "suggestd",
    "parsecd",
    "rapportd",
    "syspolicyd",
    "endpointsecurity",
    "transparencyd",
    "extensionkitservice",
    "backgroundtaskmanagementagent",
    "knowledgec",
    "biomeagent",
    "biomed",
    "coreduet",
    "duetactivityscheduler",
    "searchpartyd",
    "asd",
    "assetcache",
    "appinstalld",
    "pkd",
    "storedownloadd",
    "commerced",
    "apsd",
    "appleid",
    "airplay",
    "akd",
    "analyticsd",
    "assetsd",
    "atc",
    "audiod",
    "avconferenced",
    "bluetoothd",
    "callservicesd",
    "chronod",
    "cloudd",
    "cloudpaird",
    "cloudsharingd",
    "coreaudiod",
    "dasd",
    "diskarbitrationd",
    "distnoted",
    "fairplayd",
    "findmyd",
    "fmfd",
    "fmflocatord",
    "gamed",
    "healthd",
    "imagent",
    "itunescloudd",
    "kbd",
    "knowledgegraphd",
    "lsd",
    "mdmd",
    "mobileassetsd",
    "nfcd",
    "photoanalysisd",
    "photosensor",
    "pfd",
    "privatecloudcomputed",
    "remoted",
    "rtcreportingd",
    "screensharing",
    "securityd",
    "sharingd",
    "siriknowledged",
    "siriinferenced",
    "studentd",
    "symptomsd",
    "tailspind",
    "trustd",
    "universalcontrold",
    "usbmuxd",
    "videosubscriptionsd",
    "voicememod",
    "wifid",
    "xpcproxy",
    "triald",
    "sysmond",
    "cloudd",
    "amfid",
    "taskgated",
}

# ── User-cache entries that belong to the OS — NEVER auto-deleted ─────────────

SYSTEM_CACHE_PREFIXES: Set[str] = {
    "com.apple.",
    "geoservices",
    "familycircle",
    "familycircled",
    "cloudkit",
    "cloudkitd",
    "metadata.",
    "com.apple.appstoreagent",
    "com.apple.commerce",
    "com.apple.dt.",
    "swcagent",
    "storeassetd",
}

# ── File extensions that are safe system files (never treat as orphan) ────────

SYSTEM_FILE_EXTENSIONS: Set[str] = {
    ".plist",   # Only when under /Library/Preferences for system daemons
}

# ── Preference file patterns that are system-owned ───────────────────────────

SYSTEM_PREF_PATTERNS: Set[str] = {
    "com.apple.",
    "systemconfiguration",
    "loginwindow",
    ".globalpreferences",
    "globalpreferences",
    "nsnavigationpanel",
    "nsglobal",
}

# ── Shared components to never treat as orphan/junk ─────────────────────────

ORPHAN_ALWAYS_SKIP_PREFIXES: Set[str] = {
    "com.plausiblelabs.crashreporter",
    "com.telemetrydeck",
    "telemetrysignalcache",
}

ORPHAN_ALWAYS_SKIP_NAMES: Set[str] = {
    "default.store",
    "default.store-shm",
    "default.store-wal",
}
PROTECTED_APPLE_PREF_STEMS: Set[str] = {
    # Setup / onboarding
    "com.apple.SetupAssistant",
    "com.apple.preferences.sharing",
    "com.apple.preferences.users",
    "com.apple.SystemProfiler",
    "com.apple.MCX",
    "com.apple.ManagedClient",
    "com.apple.configurationprofiles",
    # Desktop & Dock
    "com.apple.dock",
    "com.apple.desktop",
    "com.apple.desktopservices",
    "com.apple.finder",
    "com.apple.sidebarlists",
    "com.apple.stacks",
    "com.apple.spaces",
    "com.apple.expose",
    "com.apple.missioncontrol",
    # Login / authentication
    "com.apple.loginwindow",
    "com.apple.loginitems",
    "com.apple.security",
    "com.apple.security.csp",
    "com.apple.security.sos",
    "com.apple.security.KCN",
    "com.apple.keychain",
    "com.apple.Keychain",
    "com.apple.screensaver",
    "com.apple.screencapture",
    # Touch ID / biometrics
    "com.apple.biometrickit",
    "com.apple.BiometricKit",
    # Siri & Spotlight
    "com.apple.siri",
    "com.apple.assistant",
    "com.apple.assistantd",
    "com.apple.siriinferenced",
    "com.apple.siriactionsd",
    "com.apple.siriknowledged",
    "com.apple.suggestions",
    "com.apple.spotlight",
    "com.apple.metadata",
    # System Settings / Preferences
    "com.apple.systempreferences",
    "com.apple.systemsettings",
    "com.apple.preference",
    "com.apple.controlcenter",
    "com.apple.notificationcenter",
    "com.apple.notificationcenterui",
    # Display / Graphics
    "com.apple.windowserver",
    "com.apple.coregraphics",
    "com.apple.Displays",
    "com.apple.MonitorPanel",
    "com.apple.universalaccess",
    # Sound & Audio
    "com.apple.sound",
    "com.apple.speech",
    "com.apple.audio",
    "com.apple.coreaudio",
    # Network & Connectivity
    "com.apple.airport",
    "com.apple.wifi",
    "com.apple.bluetooth",
    "com.apple.network",
    "com.apple.networkserviceproxy",
    "com.apple.InternetSharing",
    "com.apple.sharing",
    # Apple ID / iCloud
    "com.apple.appleid",
    "com.apple.iCloud",
    "com.apple.icloud",
    "com.apple.cloud",
    "com.apple.account",
    "com.apple.AppleIDAuthAgent",
    "com.apple.AppleIDAccount",
    "com.apple.SystemMigration",
    "com.apple.datamigrator",
    # FaceTime / Messages
    "com.apple.facetime",
    "com.apple.imessage",
    "com.apple.imagent",
    "com.apple.imservice",
    # Mail / Calendar / Contacts
    "com.apple.mail",
    "com.apple.Mail",
    "com.apple.calendar",
    "com.apple.iCal",
    "com.apple.ical",
    "com.apple.addressbook",
    "com.apple.Contacts",
    "com.apple.contacts",
    # Privacy & Security
    "com.apple.privacyservice",
    "com.apple.TCC",
    "com.apple.locationd",
    "com.apple.geod",
    "com.apple.GEO",
    "com.apple.adlib",
    "com.apple.AdLib",
    "com.apple.launchservices",
    "com.apple.LaunchServices",
    # Software Update
    "com.apple.softwareupdate",
    "com.apple.SoftwareUpdate",
    "com.apple.appstore",
    "com.apple.AppStore",
    "com.apple.commerce",
    # Time Machine
    "com.apple.timemachine",
    "com.apple.TimeMachine",
    # Printing
    "com.apple.print",
    "com.apple.printing",
    "com.apple.printcenter",
    "com.apple.CUPS",
    # Accessibility
    "com.apple.accessibility",
    "com.apple.Accessibility",
    "com.apple.VoiceOver",
    "com.apple.voiceover",
    # Keyboard / Input
    "com.apple.keyboard",
    "com.apple.Keyboard",
    "com.apple.HIToolbox",
    "com.apple.inputmethod",
    "com.apple.CharacterPalette",
    "com.apple.dictation",
    # App Store & MAS
    "com.apple.storeagent",
    "com.apple.storeaccount",
    "com.apple.StoreKit",
    "com.apple.appstoreagent",
    # Game Center
    "com.apple.gamecenter",
    "com.apple.gamed",
    # Photos / Media
    "com.apple.photos",
    "com.apple.Photos",
    "com.apple.iPhoto",
    "com.apple.music",
    "com.apple.Music",
    "com.apple.iTunes",
    "com.apple.itunes",
    "com.apple.itunescloud",
    "com.apple.QuickTime",
    "com.apple.quicktime",
    # Maps
    "com.apple.maps",
    "com.apple.Maps",
    # Wallet / PassKit
    "com.apple.passd",
    "com.apple.passkit",
    "com.apple.PassKit",
    # CarPlay
    "com.apple.carplay",
    "com.apple.CarPlay",
    # Device Management
    "com.apple.devicemanagement",
    "com.apple.remotemanagement",
    # Fonts
    "com.apple.fontregistry",
    "com.apple.FontRegistry",
    "com.apple.fontd",
    # Launch & Scheduler
    "com.apple.launchd",
    "com.apple.scheduler",
    "com.apple.ActivityMonitor",
    # Crash Reporter & Diagnostics
    "com.apple.crashreporter",
    "com.apple.CrashReporter",
    "com.apple.DiagnosticReports",
    "com.apple.analytics",
    # Terminal
    "com.apple.terminal",
    "com.apple.Terminal",
    # Console
    "com.apple.Console",
    # Archive Utility
    "com.apple.archiveutility",
    "com.apple.ArchiveUtility",
    # Disk Utility
    "com.apple.diskutility",
    "com.apple.DiskUtility",
    # Preview
    "com.apple.preview",
    "com.apple.Preview",
    # TextEdit
    "com.apple.textedit",
    "com.apple.TextEdit",
    # Stickies
    "com.apple.Stickies",
    # Voice Memos
    "com.apple.voicememos",
    # Notes
    "com.apple.notes",
    "com.apple.Notes",
    # Reminders
    "com.apple.reminders",
    "com.apple.Reminders",
    # Books
    "com.apple.books",
    "com.apple.iBooks",
    # Podcasts
    "com.apple.podcasts",
    "com.apple.Podcasts",
    # TV
    "com.apple.tv",
    "com.apple.TV",
    # Freeform
    "com.apple.freeform",
    # Journal
    "com.apple.journal",
    # Weather
    "com.apple.weather",
    "com.apple.Weather",
    # Stocks
    "com.apple.Stocks",
    # Clock
    "com.apple.clock",
    "com.apple.Clock",
    # Calculator
    "com.apple.calculator",
    "com.apple.Calculator",
    # Shortcuts
    "com.apple.shortcuts",
    "com.apple.Shortcuts",
    # Automator
    "com.apple.automator",
    "com.apple.Automator",
    # Dictionary
    "com.apple.dictionary",
    "com.apple.Dictionary",
    # Image Capture
    "com.apple.imagecapture",
    "com.apple.ImageCapture",
    # Help Viewer
    "com.apple.helpviewer",
    "com.apple.HelpViewer",
    # Grapher
    "com.apple.grapher",
    # QuickTime Player
    "com.apple.quicktimeplayer",
    "com.apple.QuickTimePlayer",
    # Unit Converter
    "com.apple.UnitConverter",
    # Digital Color Meter
    "com.apple.DigitalColorMeter",
    # Feedback Assistant
    "com.apple.FeedbackAssistant",
    "com.apple.feedback",
    # Migration Assistant
    "com.apple.migrationassistant",
    # Boot Camp
    "com.apple.bootcamp",
    # Parental Controls / Screen Time
    "com.apple.parentalcontrols",
    "com.apple.screentime",
    "com.apple.ScreenTime",
    "com.apple.familycontrols",
    "com.apple.FamilyControls",
    # Wallet
    "com.apple.wallet",
    # Health
    "com.apple.health",
    "com.apple.HealthKit",
    # Tips
    "com.apple.tips",
    # App Store
    "com.apple.store",
    "com.apple.Store",
    # Chess
    "com.apple.chess",
    "com.apple.Chess",
    # Optimized Battery Charging
    "com.apple.batterycharging",
    # Stage Manager
    "com.apple.stagemanager",
    # Debug / Developer
    "com.apple.dt.",
    # VPN
    "com.apple.vpn",
    # Handoff / Continuity
    "com.apple.handoff",
    "com.apple.continuity",
    # Sidecar
    "com.apple.sidecar",
    # Universal Control
    "com.apple.universalcontrol",
    # iMessage
    "com.apple.imessage",
}
