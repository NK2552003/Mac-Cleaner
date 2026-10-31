import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else { exit(2) }
let target = CommandLine.arguments[1]

var image: NSImage?
let fm = FileManager.default

if target.hasPrefix("/") {
    if fm.fileExists(atPath: target) {
        image = NSWorkspace.shared.icon(forFile: target)
    }
} else {
    // Treat as bundle identifier
    if let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: target) {
        image = NSWorkspace.shared.icon(forFile: url.path)
    }
}

// Fallback: if not found, check Trash for matching app
if image == nil {
    let trashUrl = fm.urls(for: .trashDirectory, in: .userDomainMask).first
    if let trash = trashUrl?.path {
        let base = (target as NSString).lastPathComponent.replacingOccurrences(of: ".app", with: "")
        for cand in ["\(trash)/\(base).app", "\(trash)/\(base.capitalized).app"] {
            if fm.fileExists(atPath: cand) {
                image = NSWorkspace.shared.icon(forFile: cand)
                break
            }
        }
    }
}

guard let img = image else { exit(3) }
let dimension = 128
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: dimension, pixelsHigh: dimension,
                              bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                              colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
img.draw(in: NSRect(x: 0, y: 0, width: dimension, height: dimension), from: .zero,
         operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
NSGraphicsContext.restoreGraphicsState()
guard let data = bitmap.representation(using: .png, properties: [:]) else { exit(4) }
FileHandle.standardOutput.write(data)

