import Foundation
import Darwin
public struct PhotoFileInfo: Sendable {
    public let asset: FileAsset
    public var bytes: Int64?
    public var error: String?
}
public struct PhotoDetails: Sendable {
    public var info = ImageInfo()
    public var files: [PhotoFileInfo] = []
    public var totalBytes: Int64? {
        guard !files.isEmpty else { return nil }
        var total: Int64 = 0
        for file in files {
            guard let bytes = file.bytes else { return nil }
            let addition = total.addingReportingOverflow(bytes)
            guard !addition.overflow else { return nil }; total = addition.partialValue
        }
        return total
    }
    public static func read(_ photo: PhotoGroup) -> PhotoDetails {
        var result = PhotoDetails()
        result.files = photo.files.map { asset in
            var file = PhotoFileInfo(asset: asset)
            do {
                let fd = try SafeImageSource.fileDescriptor(asset.url); defer { close(fd) }
                var status = stat()
                guard fstat(fd, &status) == 0 else { throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
                file.bytes = status.st_size
            } catch { file.error = error.localizedDescription }
            return file
        }
        func priority(_ file: FileAsset) -> Int {
            switch file.kind { case .jpeg: 0; case .raw: 1; case .export: 2; case .xmp: 3 }
        }
        let ordered = photo.files.indices.sorted {
            let a = priority(photo.files[$0]), b = priority(photo.files[$1]); return a == b ? $0 < $1 : a < b
        }
        for index in ordered where photo.files[index].kind != .xmp && result.files[index].error == nil {
            let next = ImageReader.info(photo.files[index].url)
            if !next.recognized { result.files[index].error = "当前系统未能读取此文件的图像信息。" }
            result.info.camera = result.info.camera ?? next.camera
            result.info.lens = result.info.lens ?? next.lens
            result.info.capturedAt = result.info.capturedAt ?? next.capturedAt
            result.info.shutter = result.info.shutter ?? next.shutter
            result.info.aperture = result.info.aperture ?? next.aperture
            result.info.iso = result.info.iso ?? next.iso
            result.info.focalLength = result.info.focalLength ?? next.focalLength
            result.info.exposureBias = result.info.exposureBias ?? next.exposureBias
            result.info.dimensions = result.info.dimensions ?? next.dimensions
            result.info.recognized = result.info.recognized || next.recognized
        }
        result.info.capturedAt = result.info.capturedAt ?? photo.capturedAt
        return result
    }
}
