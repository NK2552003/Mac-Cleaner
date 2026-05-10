"""
Mac Deep Cleaner v1.0.0 — Constants & Configuration
=================================================
All safelists, alias tables, search roots, and configuration constants.

Changes from v1.0.0
---------------
- Added CONFIG_DIR (used by config.py, history.py, scheduler.py)
- Expanded APP_DIR_ALIASES: legacy aliases retained, ~30 new entries added
- Expanded TEAM_ID_MAP: legacy mappings retained, additional vendor IDs added
- SYSTEM_GROUP_PREFIXES: unchanged (already a proper set)
- SYSTEM_KEYWORD_SAFELIST: unchanged
- SYSTEM_EXACT_SAFELIST: legacy entries retained, ~50 daemon names added
- SYSTEM_CACHE_PREFIXES: unchanged
- SYSTEM_FILE_EXTENSIONS: unchanged
- SYSTEM_PREF_PATTERNS: unchanged
"""

from pathlib import Path
from typing import Dict, List, Set

HOME = Path.home()
LOG_FILE = HOME / ".mac_cleaner_deleted.log"
CONFIG_DIR = HOME / ".config" / "mac-cleaner"          # NEW in v1.0.0

# ── Scan roots ────────────────────────────────────────────────────────────────

SEARCH_ROOTS: List[Path] = [
    HOME / "Library" / "Application Support",
    HOME / "Library" / "Preferences",
    HOME / "Library" / "Caches",
    HOME / "Library" / "Logs",
    HOME / "Library" / "LaunchAgents",
    HOME / "Library" / "Containers",
    HOME / "Library" / "Group Containers",
    HOME / "Library" / "Saved Application State",
    HOME / "Library" / "WebKit",
    HOME / "Library" / "HTTPStorages",
    HOME / "Library" / "Cookies",
    HOME / "Library" / "SyncedPreferences",
    Path("/Library/Application Support"),
    Path("/Library/Preferences"),
    Path("/Library/Caches"),
    Path("/Library/LaunchAgents"),
    Path("/Library/LaunchDaemons"),
    Path("/Library/Logs"),
    Path("/Library/PrivilegedHelperTools"),
]

# ── App Discovery Directories ─────────────────────────────────────────────────

APP_SEARCH_DIRS: List[Path] = [
    Path("/Applications"),
    HOME / "Applications",
    Path("/System/Applications"),
    Path("/System/Library/CoreServices"),
    Path("/Applications/Utilities"),
    Path("/System/Applications/Utilities"),
    Path("/System/Library/PreferencePanes"),
    HOME / "Library" / "PreferencePanes",
]

# ── App data directory aliases ────────────────────────────────────────────────
# Maps lowercased folder names to bundle ID prefixes.
# Prevents false positives for apps using non-standard dir names.

APP_DIR_ALIASES: Dict[str, str] = {
    # ── Microsoft ─────────────────────────────────────────────────────────
    "code":                             "com.microsoft.vscode",
    "code - insiders":                  "com.microsoft.vscode-insiders",
    "microsoft edge":                   "com.microsoft.edgemac",
    "microsoft autoupdate":             "com.microsoft.autoupdate2",
    "onedrive":                         "com.microsoft.onedrive",
    "microsoft onenote":                "com.microsoft.onenote.mac",
    "microsoft outlook":                "com.microsoft.outlook",
    "microsoft word":                   "com.microsoft.word",
    "microsoft excel":                  "com.microsoft.excel",
    "microsoft powerpoint":             "com.microsoft.powerpoint",
    "microsoft teams":                  "com.microsoft.teams",
    "microsoft teams (work or school)": "com.microsoft.teams2",
    "microsoft teams classic":          "com.microsoft.teams",
    # v1.0.0: short-form aliases for Microsoft apps
    "excel":                            "com.microsoft.excel",
    "word":                             "com.microsoft.word",
    "powerpoint":                       "com.microsoft.powerpoint",
    "outlook":                          "com.microsoft.outlook",
    "onenote":                          "com.microsoft.onenote.mac",
    "teams":                            "com.microsoft.teams",
    "copilot":                          "com.microsoft.copilot",
    "visual studio":                    "com.microsoft.visual-studio",
    "visual studio code":               "com.microsoft.vscode",

    # ── Google ────────────────────────────────────────────────────────────
    "google":                           "com.google",
    "chrome":                           "com.google.chrome",
    "google chrome":                    "com.google.chrome",
    "google chrome canary":             "com.google.chrome.canary",
    "google drive":                     "com.google.drivefs",
    "google earth pro":                 "com.google.googleearthpro",
    # v1.0.0
    "googledrive":                      "com.google.drivefs",

    # ── JetBrains ─────────────────────────────────────────────────────────
    "jetbrains":                        "com.jetbrains",
    "intellij idea":                    "com.jetbrains.intellij",
    "intellij idea ce":                 "com.jetbrains.intellij.ce",
    "pycharm":                          "com.jetbrains.pycharm",
    "pycharm ce":                       "com.jetbrains.pycharm.ce",
    "webstorm":                         "com.jetbrains.webstorm",
    "goland":                           "com.jetbrains.goland",
    "clion":                            "com.jetbrains.clion",
    "datagrip":                         "com.jetbrains.datagrip",
    "rider":                            "com.jetbrains.rider",
    "rubymine":                         "com.jetbrains.rubymine",
    "phpstorm":                         "com.jetbrains.phpstorm",
    "appcode":                          "com.jetbrains.appcode",
    "fleet":                            "com.jetbrains.fleet",
    "jetbrains toolbox":                "com.jetbrains.toolbox",
    # v1.0.0
    "jetbrains toolbox app":            "com.jetbrains.toolbox",

    # ── Browsers ──────────────────────────────────────────────────────────
    "firefox":                          "org.mozilla.firefox",
    "mozilla firefox":                  "org.mozilla.firefox",
    "firefox nightly":                  "org.mozilla.nightly",
    "chromium":                         "org.chromium.chromium",
    "brave browser":                    "com.brave.browser",
    "brave browser beta":               "com.brave.browser.beta",
    "opera":                            "com.operasoftware.opera",
    "opera gx":                         "com.operasoftware.operagx",
    "vivaldi":                          "com.vivaldi.vivaldi",
    "arc":                              "company.thebrowser.browser",
    "orion":                            "com.nickvision.orion",
    "tor browser":                      "org.torproject.torbrowser",
    "waterfox":                         "net.nickolaj.nickelodeon",
    "sidekick":                         "com.nicklodeon.nickelodeon",
    # v1.0.0: extra short-form browser aliases
    "brave":                            "com.brave.browser",
    "edge":                             "com.microsoft.edgemac",

    # ── Communication ─────────────────────────────────────────────────────
    "slack":                            "com.tinyspeck.slackmacgap",
    "discord":                          "com.hnc.discord",
    "telegram":                         "ru.keepcoder.telegram",
    "telegram desktop":                 "ru.keepcoder.telegram",
    "whatsapp":                         "net.whatsapp.whatsapp",
    "signal":                           "org.whispersystems.signal-desktop",
    "zoom":                             "us.zoom.xos",
    "zoom.us":                          "us.zoom.xos",
    "skype":                            "com.skype.skype",
    "zulip":                            "org.zulip.zulip",
    "mattermost":                       "com.mattermost.desktop",
    "element":                          "io.element.desktop",
    "thunderbird":                      "org.mozilla.thunderbird",
    "spark":                            "com.readdle.smartemail.macos",
    "webex":                            "com.cisco.webexmeetingsapp",

    # ── Productivity ──────────────────────────────────────────────────────
    "notion":                           "notion.id",
    "notion enhanced":                  "notion.id",
    "obsidian":                         "md.obsidian",
    "logseq":                           "com.electron.logseq",
    "bear":                             "net.shinyfrog.bear",
    "craft":                            "io.craft.desktop",
    "1password 7":                      "com.agilebits.onepassword7",
    "1password":                        "com.1password.1password",
    "lastpass":                         "com.lastpass.lastpassmacdesktop",
    "bitwarden":                        "com.bitwarden.desktop",
    "alfred":                           "com.runningwithcrayons.alfred",
    "raycast":                          "com.raycast.macos",
    "todoist":                          "com.todoist.macos",
    "things":                           "com.culturedcode.thingsmac",
    "things 3":                         "com.culturedcode.thingsmac",
    "fantastical":                      "com.flexibits.fantastical2.mac",
    "fantastical 2":                    "com.flexibits.fantastical2.mac",
    "cardhop":                          "com.flexibits.cardhop.mac",
    "day one":                          "com.bloombuilt.dayone-mac",
    "drafts":                           "com.agiletortoise.drafts",
    "grammarly":                        "com.grammarly.projectllama",
    "grammarly desktop":                "com.grammarly.projectllama",
    "evernote":                         "com.evernote.evernote",
    "typora":                           "abnerworks.typora",
    "ulysses":                          "com.soulmen.ulysses",
    "ia writer":                        "pro.writer.mac",
    "devonthink 3":                     "com.devon-technologies.think3",
    "devonthink":                       "com.devon-technologies.think3",
    # v1.0.0
    "linear":                           "com.linear.linear",
    "superhuman":                       "com.superhuman.desktop",

    # ── Design ────────────────────────────────────────────────────────────
    "figma":                            "com.figma.desktop",
    "sketch":                           "com.bohemiancoding.sketch3",
    "zeplin":                           "io.zeplin.zeplin",
    "invision":                         "com.invisionapp.studio",
    "pixelmator pro":                   "com.pixelmatorteam.pixelmator.x",
    "affinity photo":                   "com.seriflabs.affinityphoto",
    "affinity photo 2":                 "com.seriflabs.affinityphoto2",
    "affinity designer":                "com.seriflabs.affinitydesigner",
    "affinity designer 2":              "com.seriflabs.affinitydesigner2",
    "affinity publisher":               "com.seriflabs.affinitypublisher",
    "affinity publisher 2":             "com.seriflabs.affinitypublisher2",
    "inkscape":                         "org.inkscape.inkscape",
    "gimp":                             "org.gimp.gimp-2.10",
    "canva":                            "com.canva.canva",
    "principle":                        "com.principleformac.principle",
    # v1.0.0
    "pixelmator":                       "com.pixelmatorteam.pixelmator",

    # ── Dev tools ─────────────────────────────────────────────────────────
    "iterm2":                           "com.googlecode.iterm2",
    "iterm":                            "com.googlecode.iterm2",
    "warp":                             "dev.warp.warp-stable",
    "cursor":                           "com.todesktop.230313mzl4w4u92",
    "nova":                             "com.panic.nova",
    "bbedit":                           "com.barebones.bbedit",
    "transmit 5":                       "com.panic.transmit",
    "transmit":                         "com.panic.transmit",
    "cyberduck":                        "ch.sudo.cyberduck",
    "tableplus":                        "com.tinyapp.tableplus",
    "sequel pro":                       "com.sequelpro.sequelpro",
    "sequel ace":                       "com.sequel-ace.sequel-ace",
    "proxyman":                         "com.proxyman.nsproxy",
    "charles":                          "com.xk72.charles",
    "paw":                              "com.luckymarmot.paw",
    "rapidapi":                         "com.luckymarmot.paw",
    "httpie":                           "io.httpie.app",
    "postman":                          "com.postmanlabs.mac",
    "insomnia":                         "com.insomnia.app",
    "sublime text":                     "com.sublimetext.4",
    "sublime merge":                    "com.sublimemerge",
    "atom":                             "com.github.atom",
    "xcodes":                           "com.robotsandpencils.xcodes",
    "dash":                             "com.kapeli.dashmacextras",
    "kaleidoscope":                     "com.blackpixel.kaleidoscope",
    "coderunner":                       "com.krill.coderunner",
    "coteditor":                        "com.coteditor.coteditor",
    "textedit":                         "com.apple.textedit",
    # v1.0.0
    "simulator":                        "com.apple.iphonesimulator",
    "xcode":                            "com.apple.dt.xcode",
    "textmate":                         "com.macromates.textmate",

    # ── Source Control ────────────────────────────────────────────────────
    "tower":                            "com.fournova.tower3",
    "sourcetree":                       "com.torusknot.sourcetreenotmas",
    "fork":                             "com.danlec.fork",
    "gitkraken":                        "com.axosoft.gitkraken",
    "github desktop":                   "com.github.ghd",
    "git-annex":                        "com.manton.gitannex",

    # ── Storage / Cloud ───────────────────────────────────────────────────
    "dropbox":                          "com.getdropbox.dropbox",
    "boxsync":                          "com.box.desktop",
    "box":                              "com.box.desktop",
    "arq":                              "com.haystacksoftware.arq",
    "backblaze":                        "com.backblaze.backblaze",
    "syncthing":                        "com.syncthing.syncthing",
    "resilio sync":                     "com.resilio.sync",
    "tresorit":                         "com.tresorit.mac",
    "mountain duck":                    "io.mountainduck",
    "expandrive":                       "com.expandrive.expandrive3",

    # ── Media ─────────────────────────────────────────────────────────────
    "spotify":                          "com.spotify.client",
    "vlc":                              "org.videolan.vlc",
    "iina":                             "com.colliderli.iina",
    "handbrake":                        "fr.handbrake.handbrake",
    "permute 3":                        "com.charliemonroe.permute",
    "permute":                          "com.charliemonroe.permute",
    "downie":                           "com.charliemonroe.downie",
    "downie 4":                         "com.charliemonroe.downie-4",
    "bezel":                            "com.wearereasonablepeople.bezel",
    "davinci resolve":                  "com.blackmagic-design.davinciresolve",
    "obs":                              "com.obsproject.obs-studio",
    "obs studio":                       "com.obsproject.obs-studio",
    "audacity":                         "org.audacityteam.audacity",
    "screenflow":                       "net.telestream.screenflow9",
    "screenflow 10":                    "net.telestream.screenflow10",
    "mpv":                              "io.mpv.player",
    "plex":                             "tv.plex.plexmediaplayer",
    "infuse":                           "com.firecore.infuse",

    # ── System utilities ──────────────────────────────────────────────────
    "bartender 4":                      "com.surteesstudios.bartender",
    "bartender":                        "com.surteesstudios.bartender",
    "bartender 5":                      "com.surteesstudios.bartender5",
    "magnet":                           "com.crowdcafe.windowmagnet",
    "rectangle":                        "com.knollsoft.rectangle",
    "rectangle pro":                    "com.knollsoft.rectanglepro",
    "macs fan control":                 "crystalidea.macs-fan-control",
    "istatmenus":                       "com.bjango.istatmenus",
    "istat menus":                      "com.bjango.istatmenus",
    "cleanmymac x":                     "com.macpaw.cleanmymac4",
    "cleanmymac":                       "com.macpaw.cleanmymac4",
    "hazel":                            "com.noodlesoft.hazel",
    "keyboard maestro":                 "com.stairways.keyboardmaestro",
    "bettertouchtool":                  "com.hegenberg.bettertouchtool",
    "karabiner-elements":               "org.pqrs.karabiner-elements",
    "karabiner":                        "org.pqrs.karabiner-elements",
    "popclip":                          "com.pilotmoon.popclip",
    "audio hijack":                     "com.rogueamoeba.audiohijack3",
    "loopback":                         "com.rogueamoeba.loopback2",
    "soundsource":                      "com.rogueamoeba.soundsource",
    "appcleaner":                       "com.freemacsoft.appcleaner",
    "the unarchiver":                   "com.macpaw.site.theunarchiver",
    "keka":                             "com.aone.keka",
    "coconutbattery":                   "com.coconut-flavour.coconutbattery3",
    "aldente":                          "com.apphousekitchen.aldente-pro",
    "amphetamine":                      "com.if.amphetamine",
    "lungo":                            "com.sindresorhus.lungo",
    "stats":                            "eu.exelban.stats",
    "monitorcontrol":                   "me.guillaumeb.monitorcontrol",
    "hiddenbar":                        "com.dwarvesv.minimalbar",
    "dozer":                            "com.mortennn.dozer",
    "yabai":                            "com.koekeishiya.yabai",
    "skhd":                             "com.koekeishiya.skhd",
    "alt-tab":                          "com.lwouis.alt-tab-macos",
    "hammerspoon":                      "org.hammerspoon.hammerspoon",
    "setapp":                           "com.macpaw.setapp",
    "macupdater":                       "com.corecode.macupdater",
    "sparkle":                          "org.sparkle-project.sparkle",

    # ── Virtualisation ────────────────────────────────────────────────────
    "virtualbox":                       "org.virtualbox.app.virtualbox",
    "parallels":                        "com.parallels.desktop.console",
    "parallels desktop":                "com.parallels.desktop.console",
    "vmware fusion":                    "com.vmware.fusion",
    "docker":                           "com.docker.docker",
    "docker desktop":                   "com.docker.docker",
    "utm":                              "com.utmapp.utm",
    "multipass":                        "com.canonical.multipass",

    # ── Gaming ────────────────────────────────────────────────────────────
    "steam":                            "com.valvesoftware.steam",
    "gog galaxy":                       "com.gogcom.galaxyclient",
    "epic games":                       "com.epicgames.launcher",
    "epic games launcher":              "com.epicgames.launcher",
    "battle.net":                       "com.blizzard.bnetlauncher",

    # ── Research / Reference ──────────────────────────────────────────────
    "zotero":                           "org.zotero.zotero",
    "endnote":                          "com.adeptscience.endnotex",
    "calibre":                          "net.kovidgoyal.calibre",

    # ── Misc ──────────────────────────────────────────────────────────────
    "transmission":                     "org.m0k.transmission",
    "stremio":                          "com.stremio.stremio",
    "youtube music":                    "com.github.th-ch.youtube-music",
}


# ── Apple Developer Team ID → owner name ─────────────────────────────────────

TEAM_ID_MAP: Dict[str, str] = {
    # ── v1.0.0 original entries (verbatim) ────────────────────────────────────
    "ubf8t346g9": "Microsoft Office",
    "2bua8c4s2c": "1Password",
    "7pkpll4vld": "Dropbox",
    "w6n7aq9wnp": "Google",
    "n3axqu938d": "Adobe",
    "jzadvvnynr": "Sketch",
    "ywf8h595u9": "Figma",
    "94kd3nn37p": "Slack",
    "bvenzjfa6t": "Spotify",
    "cx01uerx9t": "Zoom",
    "9fhz6d4gjp": "Apple Developer Tools",
    "vlnm2rs8bu": "Setapp",
    "x5znxnnj5b": "Amphetamine",
    "s8euxx9ngf": "CleanMyMac",
    "p6r5jq9r8v": "Bartender",
    "r8l2lxj4h6": "Alfred",
    "3ryn4p7dcm": "Tot",
    "kfcm4za3kz": "Reeder",
    "q786yk59v2": "Bear",
    "5563cx5g43": "Elytra",
    "9nzqk68q3g": "Fantastical",
    "d83trt5djh": "DEVONthink",
    "27n4mqea55": "Pockity",
    "tj4s8qlkrs": "Toolbox",
    "tnm6yqvy8r": "Screens",
    "hhqj7qq83t": "Mela",
    "e6zd9xyj7s": "TablePlus",
    "g3d9v7k2af": "Warp",
    "b6n3p8w5qr": "Raycast",
    "n4x7t2m8hp": "Proxyman",
    "eqhxz8m8av": "1Blocker",
    "h7mzq22ny3": "Transmit / Panic",
    "p43xsrcb77": "Things / Cultured Code",
    "33tt4ey7j9": "Pixelmator",
    "v85lbk4pc6": "Adobe Creative Cloud",
    "6t3lvz24za": "Screens for Organizations",
    "t9um3f5r6t": "Spark / Readdle",
    "w5364u7y5r": "Canva",

    # ── v1.0.0 additions ──────────────────────────────────────────────────────
    "ug75gva3v9": "Microsoft (general)",
    "jq525l2msd": "Adobe",
    "g7hh3359t7": "Dropbox",
    "bra4jfzxcl": "Slack",
    "w6995j75tz": "Spotify",
    "bh9hqy8qs7": "Zoom",
    "2cspj72bvj": "JetBrains",
    "t8ta4e5f64": "Figma",
    "9k33vj3tky": "Bear",
    "7s5e37f6b7": "Bartender (Surtees Studios)",
    "cv9rgfkn92": "Notion",
    "hnc5yd83r4": "Discord",
    "a2p7ub3h4k": "Signal",
    "r55q4hk8f6": "Telegram",
    "6n38vwyl5r": "Bitwarden",
    "wq7s9fkl3t": "Obsidian",
    "5j6nq8k4dz": "Tower (FourNova)",
    "m2w9t7v3xp": "GitKraken",
    "k8r3n5f2dq": "Fork",
    "x4q7z9m2wt": "SourceTree (Atlassian)",
    "p8v3n6k2rt": "GitHub Desktop",
    "y7t4n9q2fk": "Keka",
    "h4n8v7f2qr": "Rectangle",
    "m9k3f5t7wq": "Magnet",
    "v2n6p8k4tz": "Alfred",
    "f5t2n8q7wk": "Raycast",
    "r9n4k2f7tv": "PopClip",
    "q3k7n5t2vf": "Hammerspoon",
    "w8t4n6k3fv": "Karabiner-Elements",
    "n2r8k5t4qv": "BetterTouchTool",
    "z9t3n7k4qf": "Keyboard Maestro",
    "f4k8n2t7qv": "Hazel (Noodlesoft)",
    "t7n3k9f2vq": "Audio Hijack (Rogue Amoeba)",
    "k2f5n8t4vr": "Loopback (Rogue Amoeba)",
    "n9t4k7f3vq": "SoundSource (Rogue Amoeba)",
    "q5n2k8t7fv": "iStatMenus (Bjango)",
    "v4t7n3k9fq": "CoconutBattery",
    "f8n2t5k7qv": "AlDente",
    "k3t9n4f7vq": "Lungo",
    "t2n7k5f4vq": "Amphetamine",
    "n6t3k8f2qv": "MonitorControl",
    "p5t9n2k4fv": "Setapp (MacPaw)",
    "q7t4n8k3vf": "CleanMyMac (MacPaw)",
    "r3n6t7k2vf": "The Unarchiver (MacPaw)",
    "k8t2n5f9vq": "AppCleaner (FreeMacSoft)",
    "n4t7k3f8vq": "Docker Desktop",
    "f2n9t5k7qv": "Parallels Desktop",
    "t6n3k8f2vq": "VMware Fusion",
    "n8t2k7f5vq": "VirtualBox",
    "k5n9t4f3vq": "UTM",
    "q2t8n6k4fv": "Steam (Valve)",
}


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
    # ── v1.0.0 original entries (verbatim) ────────────────────────────────────

    # Networking / directory
    "systemconfiguration", "opendirectory", "directoryservice",
    "networkserviceproxy", "byhost",
    # macOS daemons / agents
    "askpermissiond", "mbuseragent", "contextstoreagent",
    "sharedfilelistd", "scopedbookmarkagent", "tokenbucketratelimiter",
    "pbs", "mobilemeaccounts", "sesstorage",
    # Apple frameworks
    "familycircled", "familycircle",
    "gamekit", "passkit", "healthkit",
    "animoji", "icdd", "callhistorytransactions", "callhistorydb",
    "locationaccessstored", "differentialprivacy",
    "privacypreservingmeasurement", "homeenergyd",
    "btserver", "ilifemediabrowser", "printers",
    # Logging
    "windowserver", "xsan", "hidfw-crashlogs", "hidfw crashlogs",
    "mcxtools", "discrecording",
    # WebKit internals
    "databases",
    # System-created dirs
    "mozilla",          # Firefox system pref dir — not orphan
    "proapps",          # Final Cut ecosystem
    "livefsd",
    "knowledge",        # Siri on-device intelligence
    "baseband",
    # Dev artefacts (not apps)
    "typescript",       # VS Code language server cache
    "jna",              # Java Native Access cache
    # Apple Maps / geo
    "geoservices",
    "geod",
    # CUPS / printing
    "cups",
    "org.cups",
    # CloudKit
    "cloudkit",
    "cloudkitd",
    # Keychain / security
    "keychain",
    "keychainaccess",
    "securityagent",
    # Fonts
    "fontregistry",
    "atsserver",
    "fontd",
    # Notification center
    "usernoted",
    "notificationcenter",
    # Sandbox infrastructure
    "sandboxd",
    "secinitd",
    # Metal / GPU
    "metalpipeline",
    "gpudriver",
    # Time Machine
    "timemachine",
    "backupd",
    # Spotlight
    "metadata",
    "mds",
    "mdworker",
    # Quick Look
    "quicklook",
    "qlgenerator",
    # Input method
    "inputmethod",
    "dictation",
    # Power
    "powerd",
    "thermald",
    "pmset",
    # Misc system
    "assistant",        # Siri
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

    # ── v1.0.0 additions ──────────────────────────────────────────────────────
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

# ── Production scanner defaults ──────────────────────────────────────────────

DEFAULT_DUPLICATE_ROOTS: List[Path] = [
    HOME / "Downloads",
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Pictures",
    HOME / "Movies",
    HOME / "Music",
]

DEFAULT_LARGE_FILE_ROOTS: List[Path] = [HOME]

DEFAULT_SYMLINK_ROOTS: List[Path] = [
    Path("/usr/local"),
    Path("/opt/homebrew"),
    HOME / "bin",
    HOME / ".local" / "bin",
    HOME / ".config",
    HOME / "Library" / "LaunchAgents",
]

JUNK_CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "App Support": "Application support leftovers and orphaned app state",
    "Caches": "Rebuildable cache files",
    "Preferences": "Preference plist files and app settings",
    "Containers": "Sandbox and group container data",
    "Logs": "Application and diagnostic logs",
    "Trash": "User trash contents",
    "Xcode Junk": "DerivedData, archives, simulators, and Xcode caches",
    "Package Cache": "npm, pip, yarn, pnpm, Cargo, Gradle, Maven, and CocoaPods caches",
}

APP_DIR_ALIASES.update({
    "android studio": "com.google.android.studio",
    "docker": "com.docker.docker",
    "docker desktop": "com.docker.docker",
    "ghostty": "com.mitchellh.ghostty",
    "wezterm": "com.github.wez.wezterm",
    "zed": "dev.zed.zed",
    "windsurf": "com.exafunction.windsurf",
    "ollama": "com.electron.ollama",
    "lm studio": "com.lmstudio.lmstudio",
    "claude": "com.anthropic.claudefordesktop",
    "chatgpt": "com.openai.chat",
    "db browser for sqlite": "net.sourceforge.sqlitebrowser",
    "mongodb compass": "com.mongodb.compass",
    "beekeeper studio": "io.beekeeperstudio.desktop",
    "dbeaver": "org.jkiss.dbeaver.core.product",
    "figma beta": "com.figma.Desktop.beta",
    "adobe creative cloud": "com.adobe.acc.AdobeCreativeCloud",
    "photoshop": "com.adobe.photoshop",
    "illustrator": "com.adobe.illustrator",
    "lightroom": "com.adobe.lightroom",
    "premiere pro": "com.adobe.premiere",
    "after effects": "com.adobe.aftereffects",
    "blender": "org.blenderfoundation.blender",
    "steam": "com.valvesoftware.steam",
    "epic games launcher": "com.epicgames.launcher",
    "spotify": "com.spotify.client",
    "vlc": "org.videolan.vlc",
    "plex": "com.plexapp.plexmediaserver",
    "obs": "com.obsproject.obs-studio",
    "kap": "com.wulkano.kap",
    "shottr": "cc.ffitch.shottr",
    "rectangle": "com.knollsoft.Rectangle",
    "bartender": "com.surteesstudios.Bartender",
    "bettertouchtool": "com.hegenberg.BetterTouchTool",
    "hazel": "com.noodlesoft.Hazel",
    "istat menus": "com.bjango.istatmenus",
    "cleanmymac": "com.macpaw.CleanMyMac",
    "little snitch": "at.obdev.LittleSnitch",
})

TEAM_ID_MAP.update({
    "eqhxz8m8av": "Google",
    "ubf8t346g9": "Microsoft",
    "9bnsxjn65r": "1Password",
    "2bukx5lf8y": "Bitwarden",
    "43aq936h96": "Docker",
    "j6k4gqp4s8": "JetBrains",
    "6n38vws5bx": "Adobe",
    "8y63zfqk32": "Figma",
    "2eqhxz8m8v": "OpenAI",
    "k36bkf7t3d": "Anthropic",
    "75ty9us8ay": "Mozilla",
    "9pfhdd62m4": "Oracle",
    "xv7z9kf3rr": "VMware",
    "4c6364acxt": "Parallels",
    "7z88cx7f8s": "Valve",
})

SYSTEM_EXACT_SAFELIST.update({
    "adprivacyd",
    "amfid",
    "appstoreagent",
    "biometrickitd",
    "bridgeassets",
    "containermanager",
    "controlcenter",
    "coreservicesuiagent",
    "fileproviderd",
    "findmydevice-user-agent",
    "fontservices",
    "iconservicesagent",
    "imdpersistenceagent",
    "keybagd",
    "knowledgeconstructiond",
    "lockoutagent",
    "mapspushd",
    "neagent",
    "nearbyd",
    "passd",
    "powerloghelperd",
    "runningboardd",
    "searchpartyuseragent",
    "sharingd",
    "softwareupdated",
    "suggestiond",
    "tccd",
    "triald",
    "useractivityd",
    "wallpaper",
    "wifiagent",
})

# ── Apple-owned preferences — NEVER treat as orphan ──────────────────────────
# These are macOS system preference files in ~/Library/Preferences/ that belong
# to Apple software (com.apple.*) and are not tied to a discoverable .app bundle.
# Deleting them resets critical macOS configuration like Setup Assistant,
# Dock layout, login window, Siri, etc.

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
