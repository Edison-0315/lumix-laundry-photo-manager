// Development-only images with visible corner markers for native zoom/pan QA.
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
let root = URL(fileURLWithPath: CommandLine.arguments[1])
guard !FileManager.default.fileExists(atPath: root.path) else { fatalError("Fixture destination already exists") }
try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
for (name, width, height) in [("A-landscape", 3600, 2400), ("B-portrait", 1600, 3200)] {
    let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                            bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                            bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    let colors: [(CGFloat, CGFloat, CGFloat)] = [(0.85, 0.15, 0.1), (0.1, 0.7, 0.2), (0.1, 0.3, 0.9), (0.9, 0.7, 0.1)]
    for y in 0..<8 { for x in 0..<8 {
        let color = colors[(y % 2) * 2 + x % 2]
        context.setFillColor(CGColor(red: color.0, green: color.1, blue: color.2, alpha: 1))
        context.fill(CGRect(x: x * width / 8, y: y * height / 8, width: width / 8, height: height / 8))
    } }
    // Asymmetric white marker at image top-left, black marker bottom-right.
    context.setFillColor(CGColor(gray: 1, alpha: 1))
    context.fill(CGRect(x: 0, y: height - 200, width: 500, height: 200))
    context.setFillColor(CGColor(gray: 0, alpha: 1))
    context.fill(CGRect(x: width - 200, y: 0, width: 200, height: 500))
    let destination = CGImageDestinationCreateWithURL(root.appendingPathComponent(name + ".JPG") as CFURL, UTType.jpeg.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(destination, context.makeImage()!, nil)
    precondition(CGImageDestinationFinalize(destination))
}
try Data("intentional corrupt JPEG for retry UI".utf8).write(to: root.appendingPathComponent("C-broken.JPG"))
print(root.path)
