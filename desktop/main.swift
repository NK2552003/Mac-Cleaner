import AppKit
import WebKit
import Darwin
import UserNotifications

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, NSWindowDelegate, WKScriptMessageHandler, UNUserNotificationCenterDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var chrome: WindowChrome!
    private var process: Process?
    private var pipe: Pipe?
    private var output = Data()
    private var origin: URL?
    private var terminating = false
    private var opened = false
    private var presentation = WindowPresentation()
    private var statusItem: NSStatusItem?
    private var statusTimer: Timer?
    private var spaceMenuItem: NSMenuItem?
    private var pressureMenuItem: NSMenuItem?
    private var cleanupStatusMenuItem: NSMenuItem?
    private var cleanMenuItem: NSMenuItem?
    private var translations: [String: String] = [:]
    private var initialLight = false
    private var menuSources: [ObjectIdentifier: String] = [:]

    private func localized(_ source: String) -> String { translations[source] ?? source }

    private func loadNativeLanguage() {
        let support = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Mac Deep Cleaner")
        guard let data = try? Data(contentsOf: support.appendingPathComponent("settings.json")),
              let settings = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let _ = settings["theme"] else { return }
        initialLight = settings["theme"] as? String == "light"
        guard let language = settings["language"] as? String,
              language.range(of: "^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8}){0,3}$", options: .regularExpression) != nil,
              language != "en" else { return }
        let variants = language.contains("-") ? [String(language.split(separator: "-")[0]), language] : [language]
        for variant in variants {
            let bundled = Bundle.main.resourceURL?.appendingPathComponent("engine/_internal/mac_deep_cleaner/web/locales/" + variant + ".json")
            let custom = support.appendingPathComponent("locales/" + variant + ".json")
            for url in [bundled, custom].compactMap({ $0 }) {
                if let data = try? Data(contentsOf: url),
                   let pack = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let messages = pack["messages"] as? [String: String] {
                    translations.merge(messages) { _, new in new }
                }
            }
        }
    }

    private func translateMenu(_ menu: NSMenu?) {
        guard let menu = menu else { return }
        for item in menu.items where !item.isSeparatorItem {
            let key = ObjectIdentifier(item)
            let source = menuSources[key] ?? item.title
            menuSources[key] = source
            item.title = localized(source)
            if let submenu = item.submenu {
                submenu.title = item.title
                translateMenu(submenu)
            }
        }
    }


    func applicationDidFinishLaunching(_ notification: Notification) {
        loadNativeLanguage()
        UNUserNotificationCenter.current().delegate = self
        setupMenu()
        window = CleanerWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 880),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        window.title = "Mac Deep Cleaner"
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = true
        window.collectionBehavior = [.fullScreenPrimary, .managed]
        for type: NSWindow.ButtonType in [.closeButton, .miniaturizeButton, .zoomButton] {
            window.standardWindowButton(type)?.isHidden = true
        }
        window.minSize = NSSize(width: 720, height: 560)
        window.center()
        window.setFrameAutosaveName("MacDeepCleanerMainWindow")
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let userContent = configuration.userContentController
        userContent.addUserScript(WKUserScript(
            source: """
            document.addEventListener('DOMContentLoaded', () => {
                document.documentElement.classList.add('native-window');
                const t = document.documentElement.dataset.theme;
                if (t) window.webkit?.messageHandlers?.themeChange?.postMessage(t);
                const observer = new MutationObserver(() => {
                    const theme = document.documentElement.dataset.theme;
                    if (theme) window.webkit?.messageHandlers?.themeChange?.postMessage(theme);
                });
                observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
            });
            """,
            injectionTime: .atDocumentStart, forMainFrameOnly: true))
        userContent.add(self, name: "themeChange")
        userContent.add(self, name: "languageChange")
        userContent.add(self, name: "notifications")
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]
        let container = WorkspaceContentView(frame: window.contentView!.bounds, webView: webView)
        window.contentView = container
        chrome = container.chrome
        updateTheme(initialLight)
        let starting = localized("Starting Mac Deep Cleaner…").replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;")
        webView.loadHTMLString("<body style='background:\(initialLight ? "#eef1f5" : "#252525");color:\(initialLight ? "#1d2734" : "#f5f5f5");font:15px -apple-system;display:grid;place-items:center;height:90vh'>\(starting)</body>", baseURL: nil)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        setupStatusItem()
        launchEngine()
    }

    private func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem = item
        item.button?.image = NSImage(systemSymbolName: "internaldrive", accessibilityDescription: "Mac Deep Cleaner")
        item.button?.imagePosition = .imageLeading
        let menu = NSMenu()
        menu.autoenablesItems = false
        spaceMenuItem = menu.addItem(withTitle: "Checking free space…", action: nil, keyEquivalent: "")
        pressureMenuItem = menu.addItem(withTitle: "Memory pressure: checking…", action: nil, keyEquivalent: "")
        spaceMenuItem?.isEnabled = false
        pressureMenuItem?.isEnabled = false
        menu.addItem(.separator())
        let open = menu.addItem(withTitle: "Open Mac Deep Cleaner", action: #selector(showWorkspace), keyEquivalent: "")
        open.target = self
        cleanMenuItem = menu.addItem(withTitle: "One-click safe cleanup", action: #selector(menuSafeClean), keyEquivalent: "")
        cleanMenuItem?.target = self
        cleanMenuItem?.isEnabled = false
        cleanupStatusMenuItem = menu.addItem(withTitle: "Safe cleanup", action: nil, keyEquivalent: "")
        cleanupStatusMenuItem?.isEnabled = false
        let history = menu.addItem(withTitle: "Cleanup history", action: #selector(showHistory), keyEquivalent: "")
        history.target = self
        let settings = menu.addItem(withTitle: "Settings", action: #selector(showSettings), keyEquivalent: "")
        settings.target = self
        let updates = menu.addItem(withTitle: "Check for updates", action: #selector(checkUpdates), keyEquivalent: "")
        updates.target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Mac Deep Cleaner", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "")
        item.menu = menu
        translateMenu(menu)
        refreshStatus()
        statusTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.refreshStatus() }
    }

    private func refreshStatus() {
        if let stats = try? FileManager.default.attributesOfFileSystem(forPath: NSHomeDirectory()),
           let free = stats[.systemFreeSize] as? NSNumber {
            let formatted = ByteCountFormatter.string(fromByteCount: free.int64Value, countStyle: .decimal)
            statusItem?.button?.title = " " + formatted
            statusItem?.button?.toolTip = "Mac Deep Cleaner · " + localized("Free space: {size}").replacingOccurrences(of: "{size}", with: formatted)
            spaceMenuItem?.title = localized("Free space: {size}").replacingOccurrences(of: "{size}", with: formatted)
        }
        var pressure: UInt32 = 0
        var length = MemoryLayout<UInt32>.size
        let success = sysctlbyname("kern.memorystatus_vm_pressure_level", &pressure, &length, nil, 0) == 0
        let label = success ? ([1: "Normal", 2: "Warning", 4: "Critical"][Int(pressure)] ?? "Unknown") : "Unavailable"
        pressureMenuItem?.title = localized("Memory pressure: {state}").replacingOccurrences(of: "{state}", with: localized(label))
        if opened {
            webView.evaluateJavaScript("typeof BackgroundUI !== 'undefined' && BackgroundUI.poll(); void 0", completionHandler: nil)
            notificationStatus(enable: false)
            webView.evaluateJavaScript("typeof BackgroundUI !== 'undefined' ? BackgroundUI.menuStatus() : ''") { [weak self] result, _ in
                if let title = result as? String, !title.isEmpty { self?.cleanupStatusMenuItem?.title = title }
            }
            webView.evaluateJavaScript("typeof canSelect === 'function' && canSelect()") { [weak self] result, _ in
                self?.cleanMenuItem?.isEnabled = (result as? Bool) == true
            }
        }
    }

    @objc private func showWorkspace() {
        presentation.requestShow()
        NSApp.setActivationPolicy(.regular)
        if window.isMiniaturized { window.deminiaturize(nil) }
        NSApp.unhide(nil)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        refreshStatus()
    }

    @objc private func showHistory() {
        showWorkspace()
        webView.evaluateJavaScript("typeof HistoryUI !== 'undefined' && HistoryUI.open()", completionHandler: nil)
    }

    @objc private func showSettings() {
        showWorkspace()
        webView.evaluateJavaScript("typeof navigate === 'function' && navigate('settings'); void 0", completionHandler: nil)
    }

    @objc private func checkUpdates() {
        showWorkspace()
        webView.evaluateJavaScript("window.MDCNative?.checkUpdates(); void 0", completionHandler: nil)
    }

    @objc private func menuSafeClean() {
        cleanMenuItem?.isEnabled = false
        webView.evaluateJavaScript("window.MDCNative?.safeClean(); void 0", completionHandler: nil)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showWorkspace()
        return true
    }

    private func setupMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(title: "Mac Deep Cleaner", action: nil, keyEquivalent: "")
        main.addItem(appItem)
        let appMenu = NSMenu(title: "Mac Deep Cleaner")
        appMenu.addItem(withTitle: "About Mac Deep Cleaner", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        let updates = appMenu.addItem(withTitle: "Check for updates", action: #selector(checkUpdates), keyEquivalent: "")
        updates.target = self
        let settings = appMenu.addItem(withTitle: "Settings", action: #selector(showSettings), keyEquivalent: ",")
        settings.target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Mac Deep Cleaner", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        let editItem = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
        main.addItem(editItem)
        let edit = NSMenu(title: "Edit")
        edit.addItem(withTitle: "Undo", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        let windowItem = NSMenuItem(title: "Window", action: nil, keyEquivalent: "")
        main.addItem(windowItem)
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        let fullscreen = windowMenu.addItem(withTitle: "Toggle Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        fullscreen.keyEquivalentModifierMask = [.command, .control]
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowItem.submenu = windowMenu
        NSApp.windowsMenu = windowMenu
        NSApp.mainMenu = main
        translateMenu(main)
    }

    private func launchEngine() {
        guard let resources = Bundle.main.resourceURL else { fail("Application resources are missing."); return }
        let task = Process()
        task.executableURL = resources.appendingPathComponent("engine/mac-deep-cleaner-engine")
        task.arguments = ["--web", "--no-open", "--port", "0"]
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        environment["PYTHONUNBUFFERED"] = "1"
        task.environment = environment
        let outputPipe = Pipe()
        task.standardOutput = outputPipe
        task.standardError = FileHandle.nullDevice
        self.pipe = outputPipe
        outputPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil; return }
            DispatchQueue.main.async { self?.received(data) }
        }
        task.terminationHandler = { [weak self] task in
            DispatchQueue.main.async {
                guard let self = self, !self.terminating else { return }
                self.fail(self.localized("The local service stopped (status {status}). Quit and reopen the application.").replacingOccurrences(of: "{status}", with: String(task.terminationStatus)))
            }
        }
        process = task
        do { try task.run() } catch { fail(localized("Could not start the local service: {error}").replacingOccurrences(of: "{error}", with: error.localizedDescription)) }
        DispatchQueue.main.asyncAfter(deadline: .now() + 20) { [weak self] in
            guard let self = self, !self.opened, !self.terminating else { return }
            self.fail("The local service did not start. Quit and reopen the application.")
        }
    }

    private func received(_ data: Data) {
        guard !opened, output.count < 16384 else { return }
        output.append(data)
        guard let text = String(data: output, encoding: .utf8), text.contains("\n"),
              let line = text.split(separator: "\n").first(where: { $0.hasPrefix("Mac Deep Cleaner: ") }),
              let url = URL(string: String(line.dropFirst("Mac Deep Cleaner: ".count))),
              url.scheme == "http", url.host == "127.0.0.1", url.port != nil else { return }
        opened = true
        origin = url
        webView.load(URLRequest(url: url))
        output.removeAll()
    }

    private func fail(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Mac Deep Cleaner"
        alert.informativeText = localized(message)
        alert.alertStyle = .warning
        alert.addButton(withTitle: localized("Quit"))
        alert.runModal()
        NSApp.terminate(nil)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame,
              let url = message.frameInfo.request.url,
              url.scheme == "http", url.host == "127.0.0.1", url.port == origin?.port else { return }
        if message.name == "notifications", let payload = message.body as? [String: Any] {
            switch payload["action"] as? String {
            case "authorize":
                UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { [weak self] _, _ in
                    self?.notificationStatus(enable: true)
                }
            case "settings":
                if let url = URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension") { NSWorkspace.shared.open(url) }
            case "test", "deliver":
                let content = UNMutableNotificationContent()
                content.title = String((payload["title"] as? String ?? "Mac Deep Cleaner").prefix(200))
                content.body = String((payload["body"] as? String ?? "").prefix(1000))
                content.sound = .default
                let identifier = "mdc-" + (payload["id"] as? String ?? UUID().uuidString)
                UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: identifier, content: content, trigger: nil)) { [weak self] error in
                    if error != nil { self?.notificationStatus(enable: false) }
                }
            default: break
            }
        }
        if message.name == "languageChange", message.frameInfo.isMainFrame,
           let payload = message.body as? [String: Any],
           let messages = payload["messages"] as? [String: String] {
            translations = messages
            translateMenu(NSApp.mainMenu)
            translateMenu(statusItem?.menu)
            refreshStatus()
        }
        if message.name == "themeChange", let theme = message.body as? String {
            DispatchQueue.main.async {
                self.updateTheme(theme == "light")
            }
        }
    }

    private func notificationStatus(enable: Bool) {
        UNUserNotificationCenter.current().getNotificationSettings { [weak self] settings in
            let status: String
            switch settings.authorizationStatus {
            case .authorized, .provisional: status = "Enabled"
            case .denied: status = "Disabled in System Settings"
            default: status = "Off"
            }
            DispatchQueue.main.async {
                self?.webView?.callAsyncJavaScript("if (typeof BackgroundUI !== 'undefined') await BackgroundUI.authorization(status, enable)", arguments: ["status": status, "enable": enable], in: nil, in: .page, completionHandler: nil)
            }
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .list])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        DispatchQueue.main.async { self.showSettings() }
        completionHandler()
    }

    func updateTheme(_ isLight: Bool) {
        window.appearance = NSAppearance(named: isLight ? .aqua : .darkAqua)
        window.backgroundColor = isLight
            ? NSColor(srgbRed: 0xee/255.0, green: 0xf1/255.0, blue: 0xf5/255.0, alpha: 1)
            : NSColor(srgbRed: 0x25/255.0, green: 0x25/255.0, blue: 0x25/255.0, alpha: 1)
        webView.underPageBackgroundColor = window.backgroundColor
        (window.contentView as? WorkspaceContentView)?.updateTheme(isLight: isLight)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        let local = url.scheme == "http" && url.host == "127.0.0.1" && url.port == origin?.port
        let localBlob = origin.map { url.absoluteString.hasPrefix("blob:http://127.0.0.1:\($0.port ?? 0)/") } ?? false
        if navigationAction.shouldPerformDownload && (local || localBlob) {
            decisionHandler(.download)
        } else if url.absoluteString == "about:blank" || local {
            decisionHandler(.allow)
        } else if url.scheme == "https" || url.scheme == "http" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        } else { decisionHandler(.cancel) }
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction,
                 didBecome download: WKDownload) {
        download.delegate = self
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                  suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = URL(fileURLWithPath: suggestedFilename).lastPathComponent
        panel.canCreateDirectories = true
        panel.beginSheetModal(for: window) { result in
            completionHandler(result == .OK ? panel.url : nil)
        }
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        let alert = NSAlert(error: error)
        alert.beginSheetModal(for: window)
    }

    func windowWillEnterFullScreen(_ notification: Notification) { presentation.willEnter() }
    func windowWillExitFullScreen(_ notification: Notification) { presentation.willExit() }

    private func applyPresentation(_ action: WindowPresentation.Action) {
        switch action {
        case .none: break
        case .hide:
            window.orderOut(nil)
            NSApp.setActivationPolicy(.accessory)
        case .exitFullscreen: window.toggleFullScreen(nil)
        case .show: showWorkspace()
        }
    }

    func windowDidEnterFullScreen(_ notification: Notification) {
        updateWindowShape()
        applyPresentation(presentation.didEnter())
    }
    func windowDidExitFullScreen(_ notification: Notification) {
        updateWindowShape()
        applyPresentation(presentation.didExit())
    }
    func windowDidFailToEnterFullScreen(_ window: NSWindow) {
        updateWindowShape()
        applyPresentation(presentation.didExit())
    }
    func windowDidFailToExitFullScreen(_ window: NSWindow) {
        updateWindowShape()
        applyPresentation(presentation.failedExit())
    }
    private func updateWindowShape() {
        let isFS = window.styleMask.contains(.fullScreen)
        for type: NSWindow.ButtonType in [.closeButton, .miniaturizeButton, .zoomButton] {
            window.standardWindowButton(type)?.isHidden = !isFS
        }
        (window.contentView as? WorkspaceContentView)?.setFullScreen(isFS)
        webView.evaluateJavaScript("document.documentElement.classList.toggle('is-fullscreen', \(isFS));", completionHandler: nil)
    }

    func windowDidBecomeKey(_ notification: Notification) { chrome?.needsDisplay = true }
    func windowDidResignKey(_ notification: Notification) { chrome?.needsDisplay = true }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        applyPresentation(presentation.requestClose())
        // The status item keeps the local dashboard available until explicit Quit.
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard opened, !terminating else { return .terminateNow }
        webView.callAsyncJavaScript("if (typeof busy !== 'undefined' && (busy || ToolkitUI.isRunning() || Boolean(window.GhostUI?.isRunning()) || HistoryUI.isRunning() || I18n.isRunning())) return true; return !(await api('/api/prepare-quit', {})).can_quit;", arguments: [:], in: nil, in: .page) { result in
            let safeToQuit: Bool
            switch result {
            case .success(let value): safeToQuit = (value as? Bool) == false
            case .failure: safeToQuit = self.process?.isRunning != true
            }
            if !safeToQuit {
                let alert = NSAlert()
                alert.messageText = self.localized("An operation is still running")
                alert.informativeText = self.localized("Wait for the current operation to finish before quitting.")
                alert.addButton(withTitle: self.localized("Keep running"))
                alert.runModal()
                sender.reply(toApplicationShouldTerminate: false)
            } else {
                sender.reply(toApplicationShouldTerminate: true)
            }
        }
        return .terminateLater
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationWillTerminate(_ notification: Notification) {
        terminating = true
        statusTimer?.invalidate()
        pipe?.fileHandleForReading.readabilityHandler = nil
        if let task = process, task.isRunning {
            task.terminate()
            let deadline = Date().addingTimeInterval(2)
            while task.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
            if task.isRunning { kill(task.processIdentifier, SIGKILL) }
        }
    }
}

let delegate = AppDelegate()
let app = NSApplication.shared
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
