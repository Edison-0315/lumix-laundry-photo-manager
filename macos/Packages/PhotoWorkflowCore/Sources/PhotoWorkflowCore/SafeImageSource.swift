import Foundation
import Darwin
import CoreGraphics
import ImageIO

/// Hold the opened regular file throughout ImageIO decoding. The kernel rejects
/// symlinks in every path component without opening ancestors for directory reads.
enum SafeImageSource {
    private final class Reader {
        let fd: Int32
        init(_ fd: Int32) { self.fd = fd }
        deinit { close(fd) }
    }
    static func fileDescriptor(_ url: URL) throws -> Int32 {
        guard url.isFileURL else { throw CocoaError(.fileReadInvalidFileName) }
        // standardizedFileURL can rewrite /private/var to the /var symlink.
        // Keep the scanner's canonical absolute path, rejecting traversal.
        let parts = url.path.split(separator: "/").map(String.init)
        guard !parts.isEmpty, !parts.contains(".."), !parts.contains(".") else { throw CocoaError(.fileReadInvalidFileName) }
        func failure() -> NSError { NSError(domain: NSPOSIXErrorDomain, code: Int(errno)) }
        // macOS 11+ O_NOFOLLOW_ANY checks the whole path atomically. Opening
        // ancestors O_RDONLY unnecessarily requires listing permission and may
        // block in TCC even when the user chose this photo source in NSOpenPanel.
        let fd = Darwin.open(url.path, O_RDONLY | O_NOFOLLOW_ANY | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { throw failure() }
        var status = stat()
        guard fstat(fd, &status) == 0, status.st_mode & S_IFMT == S_IFREG else { close(fd); throw CocoaError(.fileReadNoPermission) }
        return fd
    }
    static func open(_ url: URL) -> CGImageSource? {
        guard let fd = try? fileDescriptor(url) else { return nil }
        var status = stat()
        guard fstat(fd, &status) == 0 else { close(fd); return nil }
        let reader = Unmanaged.passRetained(Reader(fd)).toOpaque()
        var callbacks = CGDataProviderDirectCallbacks(version: 0, getBytePointer: nil, releaseBytePointer: nil, getBytesAtPosition: { info, bytes, position, count in
            guard let info else { return 0 }
            let fd = Unmanaged<Reader>.fromOpaque(info).takeUnretainedValue().fd
            return max(0, pread(fd, bytes, count, position))
        }, releaseInfo: { info in
            if let info { Unmanaged<Reader>.fromOpaque(info).release() }
        })
        guard let provider = CGDataProvider(directInfo: reader, size: status.st_size, callbacks: &callbacks) else {
            Unmanaged<Reader>.fromOpaque(reader).release(); return nil
        }
        return CGImageSourceCreateWithDataProvider(provider, [kCGImageSourceShouldCache: false] as CFDictionary)
    }
}
