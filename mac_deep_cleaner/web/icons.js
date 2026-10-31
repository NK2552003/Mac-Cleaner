const P = {
  overview:
    '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  clean:
    '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  apps: '<rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/>',
  file: '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5"/>',
  dup: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>',
  trash:
    '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12M9 7V4h6v3"/>',
  cache: '<path d="M20 11a8 8 0 10-2.3 5.7"/><path d="M20 4v7h-7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  check: '<path d="M5 12l5 5 9-10"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  disk: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  code: '<path d="M8 8l-5 4 5 4M16 8l5 4-5 4M14 5l-4 14"/>',
  cloud: '<path d="M7 18a4 4 0 010-8 5 5 0 019.6-1A4.5 4.5 0 0117 18z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  photo:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 9"/>',
  nav_clean: '<path d="M19.5 4.5l-7 7"/><path d="M10.2 9.7l4.1 4.1c-1.100 3.200-3.800 5.600-8.300 6.200.2-4.700 1.800-7.600 4.200-10.300z"/><path d="M8.500 15.800l1.600 1.600"/><path d="M4 5.500l.6 1.400 1.400.6-1.400.6L4 9.500l-.6-1.400L2 7.500l1.400-.6z"/>',
  nav_optimize: '<path d="M4.500 17.500a8.500 8.500 0 1115 0"/><path d="M12 6.500V8M6.600 9l1.100 1.100M17.400 9l-1.100 1.100"/><path d="M12 15l3.500-5"/><circle cx="12" cy="15" r="1.400"/>',
  nav_settings: '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="17" r="2"/>',
  nav_disks: '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M5 13l2.300-7.200A2 2 0 019.200 4.500h5.600a2 2 0 011.900 1.300L19 13"/><path d="M7 16.500h.01M11 16.500h6"/>',
  nav_homebrew: '<path d="M5 9h10v9a2 2 0 01-2 2H7a2 2 0 01-2-2z"/><path d="M15 11h2.500a2 2 0 012 2v1.500a2 2 0 01-2 2H15"/><path d="M5 9c-.5-2 .8-3.600 2.500-3.600C8.500 3.800 11.500 3.800 12.500 5.400 14.200 5.400 15.500 7 15 9"/><path d="M8.500 13v4M11.500 13v4"/>',
  nav_apps: '<rect x="3" y="3" width="7.500" height="7.500" rx="2"/><rect x="3" y="13.500" width="7.500" height="7.500" rx="2"/><rect x="13.500" y="13.500" width="7.500" height="7.500" rx="2"/><path d="M17.250 3v7.500M13.500 6.750H21"/>',
  nav_big: '<path d="M12 21H7a2 2 0 01-2-2V5a2 2 0 012-2h6l5 5v3"/><path d="M13 3v5h5"/><circle cx="16.500" cy="16.500" r="3"/><path d="M18.700 18.700L21 21"/>',
  nav_dups: '<path d="M8 8V5a2 2 0 012-2h5l4 4v8a2 2 0 01-2 2h-1"/><path d="M15 3v4h4"/><rect x="4" y="8" width="11" height="13" rx="2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.500v2M12 19.500v2M2.500 12h2M19.500 12h2M5.300 5.300l1.400 1.400M17.300 17.300l1.400 1.400M18.700 5.300l-1.400 1.400M6.700 17.300l-1.400 1.400"/>',
  moon: '<path d="M20 14.500A8 8 0 019.500 4a8 8 0 1010.500 10.500z"/>',
  download: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  backup: '<path d="M4 12a8 8 0 1114 5.3"/><path d="M4 6v6h6"/>',
  camera:
    '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7l1.5-3h5L16 7"/><circle cx="12" cy="13" r="3.5"/>',
  app: '<rect x="4" y="4" width="16" height="16" rx="4"/>',
  folder:
    '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
  refresh: '<path d="M20 12a8 8 0 11-2.3-5.7"/><path d="M20 4v6h-6"/>',
  pin: '<path d="M9 4h6l-1 6 3 3H7l3-3z"/><path d="M12 13v7"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
  unlock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0"/>',
  arrow: '<path d="M5 12h14M12 5l7 7-7 7"/>',
};
const CATI = {
  "System Junk": "cache",
  Trash: "trash",
  "Large & Old Files": "file",
  "Duplicate Files": "dup",
  "Downloads & Installers": "download",
  "Unused Apps & Leftovers": "apps",
  "App Caches": "cache",
  "Mail & Message Attachments": "mail",
  "Screenshots & Podcasts": "camera",
  "Backups & Updates": "backup",
  "Cloud Files on This Mac": "cloud",
  "Developer & Pro Tools": "code",
  "Photos, Music & Media": "photo",
  "System Data": "disk",
};

P.gear = P.nav_settings;
P.sparkles = P.clean;
