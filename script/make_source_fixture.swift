// Development-only synthetic JPEG fixture; never run against a user photo directory.
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
let root = URL(fileURLWithPath: CommandLine.arguments[1])
guard !FileManager.default.fileExists(atPath: root.path) else { fatalError("Fixture destination already exists") }
for (folder, name, red, green) in [("JPEG", "A", 0.7, 0.3), ("Other", "B", 0.2, 0.6)] {
    let dir = root.appendingPathComponent(folder)
    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    let c = CGContext(data: nil, width: 1200, height: 800, bitsPerComponent: 8, bytesPerRow: 4800, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    c.setFillColor(CGColor(red: red, green: green, blue: 0.2, alpha: 1)); c.fill(CGRect(x: 0,y: 0,width:1200,height:800))
    let dest = CGImageDestinationCreateWithURL(dir.appendingPathComponent(name+".JPG") as CFURL, UTType.jpeg.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, c.makeImage()!, [kCGImagePropertyTIFFDictionary: [kCGImagePropertyTIFFMake: "Synthetic", kCGImagePropertyTIFFModel: "Test Fixture"], kCGImagePropertyExifDictionary: [kCGImagePropertyExifDateTimeOriginal: "2026:11:03 10:30:00"]] as CFDictionary)
    precondition(CGImageDestinationFinalize(dest))
}
let raw = root.appendingPathComponent("RAW")
try FileManager.default.createDirectory(at: raw, withIntermediateDirectories: true)
try Data("not a real RW2 - pairing fixture only".utf8).write(to: raw.appendingPathComponent("A.RW2"))
try Data("<xmp>synthetic</xmp>".utf8).write(to: raw.appendingPathComponent("A.RW2.xmp"))
let broken = root.appendingPathComponent("ZZBroken")
try FileManager.default.createDirectory(at: broken, withIntermediateDirectories: true)
try Data("intentionally corrupt JPEG".utf8).write(to: broken.appendingPathComponent("C.JPG"))
print(root.path)
