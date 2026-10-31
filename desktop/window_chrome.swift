import AppKit

final class WindowControl: NSButton {
    enum Kind { case close, minimize, fullscreen }
    let kind: Kind
    var hovered = false { didSet { needsDisplay = true } }

    init(kind: Kind, x: CGFloat) {
        self.kind = kind
        super.init(frame: NSRect(x: x, y: 7, width: 14, height: 14))
        isBordered = false
        title = ""
        target = self
        action = #selector(activate)
        let label = kind == .close ? "Close window" : kind == .minimize ? "Minimize window" : "Toggle full screen"
        toolTip = label
        setAccessibilityLabel(label)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        let color: NSColor
        if window?.isKeyWindow != true && !hovered {
            color = NSColor(calibratedWhite: 0.31, alpha: 1)
        } else {
            switch kind {
            case .close: color = NSColor(calibratedRed: 1, green: 0.38, blue: 0.36, alpha: 1)
            case .minimize: color = NSColor(calibratedRed: 1, green: 0.75, blue: 0.27, alpha: 1)
            case .fullscreen: color = NSColor(calibratedRed: 0.23, green: 0.80, blue: 0.40, alpha: 1)
            }
        }
        let circle = NSBezierPath(ovalIn: bounds.insetBy(dx: 1, dy: 1))
        color.setFill(); circle.fill()
        NSColor.black.withAlphaComponent(0.18).setStroke(); circle.lineWidth = 0.6; circle.stroke()
        guard hovered else { return }
        let symbol = NSBezierPath()
        symbol.lineWidth = 1.1
        symbol.lineCapStyle = .round
        NSColor.black.withAlphaComponent(0.68).setStroke()
        switch kind {
        case .close:
            symbol.move(to: NSPoint(x: 4.5, y: 4.5)); symbol.line(to: NSPoint(x: 9.5, y: 9.5))
            symbol.move(to: NSPoint(x: 4.5, y: 9.5)); symbol.line(to: NSPoint(x: 9.5, y: 4.5))
        case .minimize:
            symbol.move(to: NSPoint(x: 4, y: 7)); symbol.line(to: NSPoint(x: 10, y: 7))
        case .fullscreen:
            symbol.move(to: NSPoint(x: 4, y: 7)); symbol.line(to: NSPoint(x: 4, y: 10)); symbol.line(to: NSPoint(x: 7, y: 10))
            symbol.move(to: NSPoint(x: 7, y: 4)); symbol.line(to: NSPoint(x: 10, y: 4)); symbol.line(to: NSPoint(x: 10, y: 7))
        }
        symbol.stroke()
    }
    @objc private func activate() {
        switch kind {
        case .close: window?.performClose(nil)
        case .minimize: window?.miniaturize(nil)
        case .fullscreen:
            if NSApp.currentEvent?.modifierFlags.contains(.option) == true { window?.performZoom(nil) }
            else { window?.toggleFullScreen(nil) }
        }
    }
}

final class WindowChrome: NSView {
    private var tracking: NSTrackingArea?
    var isLight = false { didSet { needsDisplay = true } }
    let controls = [WindowControl(kind: .close, x: 14), WindowControl(kind: .minimize, x: 34), WindowControl(kind: .fullscreen, x: 54)]
    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        autoresizingMask = [.width, .minYMargin]
        controls.forEach { addSubview($0) }
        setAccessibilityRole(.toolbar)
        setAccessibilityLabel("Window controls")
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }
    override func updateTrackingAreas() {
        if let tracking = tracking { removeTrackingArea(tracking) }
        tracking = NSTrackingArea(rect: NSRect(x: 10, y: 3, width: 62, height: 22), options: [.mouseEnteredAndExited, .activeAlways], owner: self)
        addTrackingArea(tracking!)
        super.updateTrackingAreas()
    }
    override func mouseEntered(with event: NSEvent) { controls.forEach { $0.hovered = true } }
    override func mouseExited(with event: NSEvent) { controls.forEach { $0.hovered = false } }
    override func mouseDown(with event: NSEvent) {
        if event.clickCount == 2 { window?.performZoom(nil) }
        else { window?.performDrag(with: event) }
    }
    override func draw(_ dirtyRect: NSRect) {
        if isLight {
            NSColor(srgbRed: 0xda/255.0, green: 0xda/255.0, blue: 0xda/255.0, alpha: 1).setFill()
        } else {
            NSColor(srgbRed: 0x25/255.0, green: 0x25/255.0, blue: 0x25/255.0, alpha: 1).setFill()
        }
        bounds.fill()
        controls.forEach { $0.needsDisplay = true }
    }
}


// The chrome and web view share a public content container. Neither is attached
// to AppKit's private titlebar hierarchy, which changes during fullscreen.
final class CleanerWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
    override func performClose(_ sender: Any?) {
        close()
        NSApp.terminate(sender)
    }
}

final class WorkspaceContentView: NSView {
    static let chromeHeight: CGFloat = 28
    let chrome: WindowChrome
    let webView: NSView
    private(set) var isFullScreen = false

    init(frame: NSRect, webView: NSView) {
        self.webView = webView
        chrome = WindowChrome(frame: .zero)
        super.init(frame: frame)
        wantsLayer = true
        layer?.backgroundColor = CGColor(srgbRed: 0x25/255.0, green: 0x25/255.0, blue: 0x25/255.0, alpha: 1)
        layer?.masksToBounds = true
        setFullScreen(false)
        addSubview(webView)
        addSubview(chrome)
        resizeSubviews(withOldSize: .zero)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }
    func updateTheme(isLight: Bool) {
        chrome.isLight = isLight
        let bg = isLight
            ? CGColor(srgbRed: 0xda/255.0, green: 0xda/255.0, blue: 0xda/255.0, alpha: 1)
            : CGColor(srgbRed: 0x25/255.0, green: 0x25/255.0, blue: 0x25/255.0, alpha: 1)
        layer?.backgroundColor = bg
        layer?.borderColor = isLight
            ? NSColor.black.withAlphaComponent(0.12).cgColor
            : NSColor.white.withAlphaComponent(0.13).cgColor
        needsDisplay = true
    }
    override func resizeSubviews(withOldSize oldSize: NSSize) {
        // In fullscreen mode, the native hover menubar/titlebar manages actions,
        // so hide our in-window custom chrome strip and expand webView to 100%.
        if isFullScreen {
            chrome.frame = .zero
            chrome.isHidden = true
            webView.frame = bounds
        } else {
            chrome.isHidden = false
            let height = min(Self.chromeHeight, bounds.height)
            chrome.frame = NSRect(x: 0, y: bounds.height - height, width: bounds.width, height: height)
            webView.frame = NSRect(x: 0, y: 0, width: bounds.width, height: max(0, bounds.height - height))
        }
    }
    func setFullScreen(_ fullScreen: Bool) {
        isFullScreen = fullScreen
        chrome.isHidden = fullScreen
        layer?.cornerRadius = fullScreen ? 0 : 16
        layer?.borderWidth = fullScreen ? 0 : 1
        layer?.borderColor = NSColor.white.withAlphaComponent(0.13).cgColor
        needsLayout = true
        resizeSubviews(withOldSize: bounds.size)
    }
}
