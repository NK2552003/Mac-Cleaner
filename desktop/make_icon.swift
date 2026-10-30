import AppKit
import Foundation

let destination = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
let inputPath = CommandLine.arguments[2]
guard let character = NSImage(contentsOfFile: inputPath) else {
    fatalError("Could not load image at \(inputPath)")
}

for points in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = points * scale
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
                                      bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                      isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        let size = CGFloat(pixels)
        let inset = size * 0.05

        // macOS Squircle tile background with sleek dark styling
        let tilePath = NSBezierPath(roundedRect: NSRect(x: inset, y: inset, width: size - 2*inset, height: size - 2*inset),
                                    xRadius: size * 0.224, yRadius: size * 0.224)
        NSColor(srgbRed: 0x1f/255.0, green: 0x22/255.0, blue: 0x26/255.0, alpha: 1.0).setFill()
        tilePath.fill()

        // Soft subtle inner border highlight
        NSColor.white.withAlphaComponent(0.08).setStroke()
        tilePath.lineWidth = max(1.0, size * 0.012)
        tilePath.stroke()

        // Draw Totoro character centered inside the app icon squircle
        character.draw(in: NSRect(x: size * 0.14, y: size * 0.12, width: size * 0.72, height: size * 0.76),
                       from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)

        NSGraphicsContext.restoreGraphicsState()
        let data = bitmap.representation(using: .png, properties: [:])!
        let name = "icon_\(points)x\(points)" + (scale == 2 ? "@2x" : "") + ".png"
        try data.write(to: destination.appendingPathComponent(name))
    }
}
