import AppKit
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, NSWindowDelegate, WKScriptMessageHandler {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var chrome: WindowChrome!
    private var process: Process?
    private var pipe: Pipe?
    private var output = Data()
    private var origin: URL?
    private var terminating = false
    private var opened = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupMenu()
        window = CleanerWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 880),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        window.title = "Mac Deep Cleaner"
        window.delegate = self
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
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]
        let container = WorkspaceContentView(frame: window.contentView!.bounds, webView: webView)
        window.contentView = container
        chrome = container.chrome
        webView.loadHTMLString("<body style='background:#181818;color:#f5f5f5;font:15px -apple-system;display:grid;place-items:center;height:90vh'>Starting Mac Deep Cleaner…</body>", baseURL: nil)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        launchEngine()
    }

    private func setupMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About Mac Deep Cleaner", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Mac Deep Cleaner", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "Edit")
        edit.addItem(withTitle: "Undo", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        let windowItem = NSMenuItem()
        main.addItem(windowItem)
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        let fullscreen = windowMenu.addItem(withTitle: "Toggle Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        fullscreen.keyEquivalentModifierMask = [.command, .control]
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowItem.submenu = windowMenu
        NSApp.windowsMenu = windowMenu
        NSApp.mainMenu = main
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
                self.fail("The local service stopped (status \(task.terminationStatus)). Quit and reopen the application.")
            }
        }
        process = task
        do { try task.run() } catch { fail("Could not start the local service: \(error.localizedDescription)") }
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
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Quit")
        alert.runModal()
        NSApp.terminate(nil)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "themeChange", let theme = message.body as? String {
            DispatchQueue.main.async {
                self.updateTheme(theme == "light")
            }
        }
    }

    func updateTheme(_ isLight: Bool) {
        window.appearance = NSAppearance(named: isLight ? .aqua : .darkAqua)
        window.backgroundColor = isLight
            ? NSColor(srgbRed: 0xda/255.0, green: 0xda/255.0, blue: 0xda/255.0, alpha: 1)
            : NSColor(srgbRed: 0x25/255.0, green: 0x25/255.0, blue: 0x25/255.0, alpha: 1)
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

    func windowDidEnterFullScreen(_ notification: Notification) {
        for type: NSWindow.ButtonType in [.closeButton, .miniaturizeButton, .zoomButton] {
            window.standardWindowButton(type)?.isHidden = false
        }
        updateWindowShape()
    }
    func windowDidExitFullScreen(_ notification: Notification) {
        for type: NSWindow.ButtonType in [.closeButton, .miniaturizeButton, .zoomButton] {
            window.standardWindowButton(type)?.isHidden = true
        }
        updateWindowShape()
    }
    private func updateWindowShape() {
        let isFS = window.styleMask.contains(.fullScreen)
        (window.contentView as? WorkspaceContentView)?.setFullScreen(isFS)
        webView.evaluateJavaScript("document.documentElement.classList.toggle('is-fullscreen', \(isFS));", completionHandler: nil)
    }

    func windowDidBecomeKey(_ notification: Notification) { chrome?.needsDisplay = true }
    func windowDidResignKey(_ notification: Notification) { chrome?.needsDisplay = true }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        // Keep the window visible while the operation guard decides whether to quit.
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard opened, !terminating else { return .terminateNow }
        webView.evaluateJavaScript("typeof busy !== 'undefined' && (busy || Boolean(S.busy) || (typeof ToolkitUI !== 'undefined' && ToolkitUI.isRunning()) || Boolean(window.GhostUI?.isRunning()))") { value, _ in
            if (value as? Bool) == true {
                let alert = NSAlert()
                alert.messageText = "An operation is still running"
                alert.informativeText = "Wait for the current operation to finish before quitting."
                alert.addButton(withTitle: "Keep running")
                alert.runModal()
                sender.reply(toApplicationShouldTerminate: false)
            } else {
                sender.reply(toApplicationShouldTerminate: true)
            }
        }
        return .terminateLater
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        terminating = true
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
