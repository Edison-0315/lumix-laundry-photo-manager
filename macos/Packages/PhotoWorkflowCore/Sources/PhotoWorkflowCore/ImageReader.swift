import Foundation
import ImageIO
import CoreGraphics
import UniformTypeIdentifiers
public struct ImageInfo: Sendable {
    public var capturedAt: String?
    public var camera: String?
    public var lens: String?
    public var shutter: String?
    public var aperture: String?
    public var iso: String?
    public var focalLength: String?
    public var exposureBias: String?
    public var dimensions: String?
    public var recognized = false
    public init() {}
}
public enum ImageReader {
    static func metadata(_ props: [CFString: Any]) -> ImageInfo {
        var info = ImageInfo(); info.recognized = true
        let exif = props[kCGImagePropertyExifDictionary] as? [CFString: Any] ?? [:]
        let tiff = props[kCGImagePropertyTIFFDictionary] as? [CFString: Any] ?? [:]
        func text(_ value: Any?) -> String? {
            guard let raw = value as? String else { return nil }
            let result = raw.trimmingCharacters(in: .whitespacesAndNewlines.union(.controlCharacters))
            return result.isEmpty ? nil : result
        }
        func number(_ value: Any?) -> Double? {
            guard let value = value as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID() else { return nil }
            return value.doubleValue.isFinite ? value.doubleValue : nil
        }
        func formatted(_ value: Double) -> String {
            String(format: "%.6g", locale: Locale(identifier: "en_US_POSIX"), value == 0 ? 0 : value)
        }
        func positive(_ key: CFString) -> Double? {
            guard let value = number(exif[key]), value > 0 else { return nil }; return value
        }
        let make = text(tiff[kCGImagePropertyTIFFMake]), model = text(tiff[kCGImagePropertyTIFFModel])
        info.camera = model ?? make
        if let make, let model, !model.lowercased().hasPrefix(make.lowercased()) { info.camera = make + " " + model }
        info.lens = text(exif[kCGImagePropertyExifLensModel])
        for candidate in [exif[kCGImagePropertyExifDateTimeOriginal], exif[kCGImagePropertyExifDateTimeDigitized], tiff[kCGImagePropertyTIFFDateTime]] {
            guard let raw = text(candidate) else { continue }
            let date = String(raw.prefix(19))
            guard date.range(of: #"^[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"#, options: .regularExpression) != nil else { continue }
            let parts = date.components(separatedBy: CharacterSet(charactersIn: ": ")).compactMap(Int.init)
            var calendar = Calendar(identifier: .gregorian); calendar.timeZone = TimeZone(secondsFromGMT: 0)!
            let components = DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: parts[3], minute: parts[4], second: parts[5])
            guard parts[0] > 0, components.isValidDate(in: calendar) else { continue }
            info.capturedAt = date.prefix(10).replacingOccurrences(of: ":", with: "-") + "T" + date.suffix(8)
            break
        }
        if let value = positive(kCGImagePropertyExifExposureTime) {
            let reciprocal = (1 / value).rounded()
            if value < 1, reciprocal >= 1, reciprocal <= 100000, abs(value * reciprocal - 1) < 0.000001 {
                info.shutter = "1/\(Int(reciprocal)) s"
            } else { info.shutter = formatted(value) + " s" }
        }
        if let value = positive(kCGImagePropertyExifFNumber) { info.aperture = "f/" + formatted(value) }
        if let value = positive(kCGImagePropertyExifFocalLength) { info.focalLength = formatted(value) + " mm" }
        let ratings = (exif[kCGImagePropertyExifISOSpeedRatings] as? [Any])?.first ?? exif[kCGImagePropertyExifISOSpeedRatings]
        if let value = [ratings, exif[kCGImagePropertyExifISOSpeed]].compactMap(number).first(where: { $0 > 0 }) { info.iso = formatted(value) }
        if let value = number(exif[kCGImagePropertyExifExposureBiasValue]) { info.exposureBias = (value >= 0 ? "+" : "") + formatted(value) + " EV" }
        if let width = number(props[kCGImagePropertyPixelWidth]), let height = number(props[kCGImagePropertyPixelHeight]),
           width > 0, height > 0, width < Double(Int.max), height < Double(Int.max), width.rounded() == width, height.rounded() == height {
            let swap = (5...8).contains(number(props[kCGImagePropertyOrientation]) ?? 1)
            info.dimensions = swap ? "\(Int(height)) × \(Int(width))" : "\(Int(width)) × \(Int(height))"
        }
        return info
    }
    public static func info(_ url: URL) -> ImageInfo {
        guard let source = SafeImageSource.open(url),
              let props = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any] else { return ImageInfo() }
        return metadata(props)
    }
    public static func preview(_ photo: PhotoGroup, maxPixel: Int) throws -> Data {
        for asset in photo.files.sorted(by: { ($0.kind == .jpeg ? 0 : 1) < ($1.kind == .jpeg ? 0 : 1) }) where asset.kind != .xmp {
            guard let source = SafeImageSource.open(asset.url),
                  let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceCreateThumbnailWithTransform: true, kCGImageSourceThumbnailMaxPixelSize: max(80, min(maxPixel, 4096)), kCGImageSourceShouldCacheImmediately: true] as CFDictionary) else { continue }
            let data = NSMutableData()
            guard let destination = CGImageDestinationCreateWithData(data, UTType.jpeg.identifier as CFString, 1, nil) else { continue }
            CGImageDestinationAddImage(destination, image, [kCGImageDestinationLossyCompressionQuality: 0.88] as CFDictionary)
            if CGImageDestinationFinalize(destination) { return data as Data }
        }
        throw CocoaError(.fileReadCorruptFile, userInfo: [NSLocalizedDescriptionKey: "无法预览此照片；原文件仍可保留，RAW 支持取决于当前系统。"])
    }
}
