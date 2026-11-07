/* Regenerate the allowlisted, privacy-safe UI catalog. npm install --prefix /tmp/mdc-i18n acorn */
const fs = require('fs'), path = require('path'), acorn = require('acorn');
const {execFileSync} = require('node:child_process');
const root=path.join(__dirname,'../mac_deep_cleaner/web'), messages=new Set();
function add(text) {
  if(text.startsWith('ghosts:{')) return; // Animation identity, not UI text.
  text=text.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim();
  // Commands and SQL are implementation data, never translated display prose.
  if(/^(?:sudo|brctl|defaults|launchctl|diskutil|tmutil|xattr|mdutil|killall|qlmanage|chmod|chown)\s/.test(text))return;
  if(/^(?:INSERT(?: OR REPLACE| OR IGNORE)? INTO|SELECT .+ FROM|CREATE TABLE|UPDATE .+ SET|DELETE FROM|PRAGMA)\b/i.test(text))return;
  if(/^(?:\[|meta\[|Library\/)|^(?:\d+px\s*)+$/.test(text))return;
  if(/^(?:APFS|RAID|SMART|OS)[A-Z][A-Za-z]+$/.test(text))return;
  if(/[\n\r\\]/.test(text)||text.startsWith('/')||text.startsWith('~'))return;
  if(text.startsWith('"')||text.endsWith('"')||text.startsWith("'")||text.endsWith("'"))return;
  if(/^[%&#;]/.test(text)||/;\s*--/.test(text)||text.startsWith('(')||text.endsWith('='))return;
  if(/^[\w./-]+$/.test(text) && /[a-z][A-Z]|[_/]|[.]/.test(text) && !/^[A-Z][a-z]+(?:-[a-z]+)?\.$/.test(text))return;
  if(/^[KMGTP]?B(?: RAM)?[) ·]*$/.test(text))return;
  if(text.startsWith('-') || text.includes('|'))return;
  if(text.startsWith('.')||text.startsWith(')')||text.endsWith('Error'))return;
  const plain = text.replace(/\{\w+\}/g, 'VALUE');
  if(text.length<2||text.length>1800||!/[a-z]{2}/i.test(text)||/[{}<>]|\$\{|(?:https?:|\/api\/|data-)/.test(plain))return;
  if(/^[a-z0-9_./:#-]+$/.test(text)||/^[A-Z_ ]+$/.test(text))return;
  messages.add(text);
}
function extract(value) {
  if(!value.includes('<')) add(value);
  else {
    for(const match of value.matchAll(/(?:^|>)([^<>]+)(?=<|$)/g))add(match[1]);
    for(const match of value.matchAll(/(?:title|aria-label|placeholder)="([^"]+)"/g))add(match[1]);
  }
}
function visit(node) {
  if(!node||typeof node!=='object')return;
  if(node.type==='VariableDeclarator'&&['translations','quickList'].includes(node.id?.name))return;
  if(node.type==='Literal'&&typeof node.value==='string')extract(node.value);
  if(node.type==='TemplateLiteral') {
    // Extract complete messages around interpolations, not just English fragments.
    const value = node.quasis.map((q,i) => (q.value.cooked || '') + (i < node.expressions.length ? `{${i}}` : '')).join('');
    extract(value);
  }
  if(node.type==='TemplateElement')extract(node.value.cooked||'');
  for(const [key,value] of Object.entries(node))if(key!=='start'&&key!=='end') {
    if(Array.isArray(value))value.forEach(visit);else if(value&&typeof value==='object')visit(value);
  }
}
for(const name of fs.readdirSync(root).filter(n=>n.endsWith('.js'))) visit(acorn.parse(fs.readFileSync(path.join(root,name),'utf8'),{ecmaVersion:'latest'}));
extract(fs.readFileSync(path.join(root,'index.html'),'utf8'));
for(const match of fs.readFileSync(path.join(__dirname,'../desktop/main.swift'),'utf8').matchAll(/(?:withTitle: |localized\(|fail\()"([^"]+)"/g))add(match[1]);
// Translation dictionaries themselves include canonical navigation labels.
const i18n=acorn.parse(fs.readFileSync(path.join(root,'i18n.js'),'utf8'),{ecmaVersion:'latest'});
function keys(node) {
 if(!node||typeof node!=='object')return;
 if(node.type==='Property'&&node.key.type==='Literal'&&typeof node.key.value==='string'&&node.value.type==='ArrayExpression')add(node.key.value);
 for(const v of Object.values(node))if(Array.isArray(v))v.forEach(keys);else if(v&&typeof v==='object')keys(v);
}
keys(i18n);
// Include static scanner explanations, maintenance reviews, and backend errors.
// Parse source files, never runtime scan results or files on the user's Mac.
const python = `import ast,json,pathlib
values=[]
for path in pathlib.Path('mac_deep_cleaner').rglob('*.py'):
 tree=ast.parse(path.read_text())
 docs=set()
 for node in ast.walk(tree):
  if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and node.body:
   first=node.body[0]
   if isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant) and isinstance(first.value.value,str): docs.add(id(first.value))
 for node in ast.walk(tree):
  if isinstance(node,ast.Constant) and isinstance(node.value,str) and id(node) not in docs:
   value=node.value
   if value.lstrip()[:1].isupper() or ('{' in value and len(value.split())>=3): values.append(value)
  if isinstance(node,ast.JoinedStr):
   parts=[]
   for part in node.values:
    parts.append(part.value if isinstance(part,ast.Constant) else '{'+str(len(parts))+'}')
   value=''.join(parts)
   if len(value.split())>=3: values.append(value)
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Spec':
   for index in (0,3,4,5):
    if len(node.args)>index and isinstance(node.args[index],ast.Constant) and isinstance(node.args[index].value,str): values.append(node.args[index].value)
print(json.dumps(values))`;
for(const value of JSON.parse(execFileSync('python3',['-c',python],{cwd:path.join(__dirname,'..'),encoding:'utf8'})))add(value);
for(const value of [
  'Risk','Explanation','Path','Storage review',
  'Edit','Window','Normal','Warning','Critical','Free space: {size}','Memory pressure: {state}',
  'Keep running','An operation is still running','Wait for the current operation to finish before quitting.',
  'Application Support','Caches','Preferences','Containers','Group Containers','Saved State','Logs','HTTPStorages',
  'moved','formula','cask','started','stopped','Indexing enabled.',
  '{size} combined footprint','Evidence score {score}/100.','Analysis source: {source}',
  'restored','trashed','missing','changed','image','video','on','off','running','stopped',
  'Safe','Caution','Risky','Clean up','Scan','Scanning','Rescan','Scan in progress','Scan complete',
  'Free space','Memory pressure','Total space','Available space','Storage cleanup','Optimize your Mac',
  'Disks & volumes','Homebrew','Applications','Large files','Duplicates','Ghost Files','Settings',
  'Cleanup','Apps','Optimize','Disks','Ghosts','Mac Deep Cleaner','This Mac','Developer mode',
  'Developer mode: on','Developer mode: off','Connecting','Disconnected','Clear','Clear selection','Review cleanup',
  'Working…','Select all','Deselect all','Select caution items','Explore your files','Sorted by size','Show more',
  'Protected','macOS','Active','Read-only','Available for review','Location','What happens if removed',
  'Original copy kept','Terminal command','A closer look','Add to cleanup','Remove from selection','Reveal in Finder',
  'Copy path','Keep out of future scans','Cancel','Confirm','Close','Done','Delete','Restore','Enable','Disable',
  'Refresh','Open Login Items','Cleanup history','No recorded cleanup yet.',
  'Ghost allowlist','Remove from allowlist','No dismissed ghosts.',
  'Up to 1,000 recent Trash moves. Restore is available while the recorded item is unchanged and its original location is free. Permanent deletion and command-based cleanup cannot be undone.',
  'Dismissed Ghost Files stay off future Ghost scans. Remove an entry to reconsider it.',
  'Nothing is removed until you review and confirm. Some items need extra care.',
  'Time','Used','Free','Homebrew packages & services','Casks','Formulae','Services','Outdated','Installed','Leaves',
  'Upgrade','Uninstall','Start','Stop','Restart','Verify filesystem','Verify partition map','Mount','Unmount','Eject',
  'Rename','Add APFS volume','Erase disk','Partition disk','Your Mac, at a glance','Everyday maintenance','Developer tools',
  'Processes using CPU','System details','macOS controls','Operation results','Activity Monitor','Manage login items',
  'Some apps leave a little behind.','Likely safe','Review first','Locked','Review in Ghost Files','Skip to content',
  'Close navigation','Expand sidebar','Collapse sidebar','Selected items','Item details','Appearance','Theme',
  'Switch between a dark and a light workspace.','Light mode','Dark mode','Developer options',
  'Show low-level command details and developer tools.','Language / भाषा / Idioma','Interface language',
  'Search languages','Search by name or language code','Apply language','Quick switch','Test language pack',
  'English source interface.','Active language','Local pack','Experimental',
  'Find leftovers from apps you have deleted. Review each one before moving it to the Trash.',
  'Ghosts (no AI)','Ghosts + AI narration','Open Ghost Files',
  'Off by default. No Ghost Files scanning, AI probing, or downloads run while disabled.',
  'Local AI narration','Set up AI narration','Save AI options','Remove AI components',
  'Start Ollama automatically when needed, after setup consent',
  'Stop Ollama when I quit, only if Mac Deep Cleaner started it',
  'Turning Ghost Files off keeps installed AI components. Removal only offers components created by Mac Deep Cleaner.',
  'Generate a language pack with Google Cloud Translation','Import or share an offline language pack',
  'Import language pack','Export current pack','Download English template',
  'Google Cloud Translation API key (never saved)','Generate selected language','Storage & Maintenance',
  'About Mac Deep Cleaner','All scanning, analysis, and maintenance runs locally on your Mac.',
  'Disk Used','Original location occupied','macOS Native','No recorded cleanup yet.','Cleaned items will appear here for one-click restore.',
  'No dismissed ghosts.','extension records','No readable profile found','Review slim copy','Additional languages to keep',
  'Save rules','Example rule','Ghost allowlist','Remove from allowlist','Loading feature settings…',
  'Only known interface messages are accepted; no HTML or code.',
  'Optional features still in testing. Off by default.',
  'Heat scale','Very large','Moderate','Smaller',
  'Close details','Close application details','Close confirmation','Confirmation phrase','Close disk setup','Close package details',
  'items selected','processed.','days ago','months ago','years ago','Today','Not recorded',
  'Shared by','roots','dependencies','dependency','unused','formulae','casks','measured','packages',
  'installed','swap used','total capacity','in container','Not reported','in extra copies','copies found','Keeping','Select duplicate',
  'Delete permanently instead of using Trash','Permanent deletion cannot be undone.','Terminal action needed',
  'These items need administrator access. The commands have not been run.','No files were removed. The items may have changed since the scan.',
  'Quit this app before uninstalling it or removing its application bundle.','What this app stores','No stored data found',
  'Remove selected parts','Application files go to the Trash. You’ll review the removal first.','Version unavailable',
  'Files are moved to the Trash by default. Review the selection before continuing.','Risky items may contain personal data that cannot be regenerated.',
  'Remove selected items','Move to Trash','The scan changed. Review your new results before cleaning.',
  'Checking…','Checked','Operation results','This session','Running…','Completed','Failed',
  'Keep Mac Deep Cleaner open. Some operations take several minutes. Check for a macOS permission dialog.',
  'Waiting for command output…','Checking your Mac…','Health check unavailable','Refresh to read memory, storage, battery, and process activity.',
  'Your Mac, at a glance','Export report','Memory size unavailable','Storage available','Background definitions',
  'Launch agents and daemons; not a running count',
  'macOS manages memory automatically. These tools diagnose issues and perform specific maintenance; they do not promise a speed boost.',
  'Start here','Your startup storage is getting full','Keep room for your next project',
  'Review caches, downloads, and large files before removing them.','Review storage','Memory pressure is normal','Check apps using memory',
  'Inspect CPU and memory use, then quit apps you no longer need.','Choose what starts with your Mac',
  'Review login items and background activity in System Settings.','Review developer files','Requires','Review task','Run check',
  'Processes using CPU','Sampled at refresh. CPU can exceed 100% across multiple cores.','Process','Memory','No process data available.',
  'System details','Battery and power','Uptime and load','Spotlight','Unavailable',
  'These files define background tasks. Presence does not mean a task is enabled or running.','No definitions found.',
  'Some checks were unavailable','Reading disk information…','Disk information unavailable',
  'Connect an external drive or refresh to inspect your Mac’s storage.','No disks available','Refresh after connecting a drive.',
  'Disk tools require macOS.','Your storage','Hide system volumes','Show system volumes','Startup volume','Internal drive','External drive',
  'Shared APFS container','Managed by macOS','Volume','Recovery, boot, and system partitions are hidden. They remain protected.',
  'Encrypted','Startup snapshot','Storage usage','Other volumes & metadata','Mount point','Not mounted','Type','Access',
  'Read and write','Read-only / locked','SMART status','Roles','None','UUID',
  'Erasing or repartitioning removes all data on the selected physical disk. Back up the drive first.',
  'First Aid, encryption & advanced layouts',
  'Use Disk Utility for repairs, encrypted volumes, secure erase where supported, or resizing existing partitions.',
  'Open Disk Utility','Reconnects and layout changes require a fresh review.','Partition','Format','Size in GB',
  'Uses the remaining space','Add partition','Remove last','Review operation','Homebrew preview',
  'I have backed up everything I need from this disk.','This review expires in five minutes.','Command details',
  'Packages','Dependency groups','Heaviest','Updates','Tidy','Services','Pinned','Disabled upstream','Deprecated','Update:','Unknown',
  'Why installed?','No matching packages','Try another search or filter, or refresh after changing Homebrew.',
  'Know why it’s installed. Keep the packages you need.','Reading Homebrew…','Reading your Homebrew environment…',
  'Homebrew inventory unavailable','Collecting installed packages, dependency receipts, sizes, and service status. Large installations can take a minute.',
  'Homebrew is not installed','Homebrew installation guide','inventory notes','package removal disabled',
  'A smaller environment, with a review at each step','Review unused dependencies','Review removal','Review caches and old versions',
  'Preview cleanup','No services found','Installed packages with Homebrew service definitions will appear here.',
  'Search packages, descriptions or taps','All packages','Shared dependencies','Pinned formulae',
  'Each group starts with a requested or protected package. Shared dependencies can appear in several groups; the environment total counts each package once.',
  'Used by this root','No installed runtime dependencies recorded.',
  'Formulae ranked by allocated Cellar size, including old installed versions. Cask applications moved outside Caskroom are excluded.',
  'Available updates from local Homebrew metadata. This is not a vulnerability scan. Self-updating and latest-version casks follow Homebrew’s normal update rules.',
  'Update status is incomplete. Refresh metadata, then retry the inventory.','Update metadata','Run brew doctor','Export Brewfile',
  'Export JSON','Why it’s installed','Needed by these roots','Installed','Measured size','Update','Service','No update reported',
  'Upgrade','Unpin','Pin','Mark as dependency','Keep','Uninstall','Direct installed dependencies','Reverse dependency tree',
  'Each indented package depends on the one above it. Repeated branches are collapsed.','Cycle','Shown above',
  'Some apps leave a little behind.','Likely safe','Review first','Locked','ghost','ghosts',
  'Moving files to Trash keeps them recoverable; space is freed when you empty it yourself.',
  'Banish all safe items','Banish','Banish safe items on this page','safe items on this page','Show','resting',
  'Search by name or path','All verdicts','Sort by size','Sort by name','Sort by date','Page','of','Previous page','Next page',
  'No ghost files found','Your Mac has no detected leftovers from uninstalled apps.','Scanning for leftovers…',
  'Discovering orphaned application support, caches, preferences, and logs.','Rescan ghosts','Local AI narration','Set up AI narration',
  'AI narration is ready on this Mac.','AI: not connected. Plain descriptions are available offline.','Save AI options',
  'Remove AI components','Dismiss'
]) messages.add(value);
const sorted=[...messages].sort();fs.writeFileSync(path.join(root,'messages.json'),JSON.stringify(sorted,null,2)+'\n');
console.log(`${sorted.length} static UI messages extracted.`);
