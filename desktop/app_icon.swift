import AppKit
import Foundation

guard CommandLine.arguments.count == 2 else { exit(2) }
let path = CommandLine.arguments[1]
guard path.hasSuffix(".app"), FileManager.default.fileExists(atPath: path) else { exit(3) }
let image = NSWorkspace.shared.icon(forFile: path)
let dimension = 128
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: dimension, pixelsHigh: dimension,
                              bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                              colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
image.draw(in: NSRect(x: 0, y: 0, width: dimension, height: dimension), from: .zero,
           operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
NSGraphicsContext.restoreGraphicsState()
guard let data = bitmap.representation(using: .png, properties: [:]) else { exit(4) }
FileHandle.standardOutput.write(data)
