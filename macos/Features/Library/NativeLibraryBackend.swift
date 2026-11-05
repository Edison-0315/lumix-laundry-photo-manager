import Foundation

struct NativeBackendError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
/// Process access is locked; only NativeLibraryBackend reads stdout or changes pipes.
private final class BackendCancellation: @unchecked Sendable {
    private let lock = NSLock()
    private var process: Process?
    private var ready = false
    func install(_ process: Process?, ready: Bool = false) {
        lock.lock(); defer { lock.unlock() }; self.process = process; self.ready = ready
    }
    func interrupt() {
        lock.lock(); defer { lock.unlock() }
        if ready, let process, process.isRunning { process.interrupt() }
    }
}

/// Synchronous requests on this actor serialize whole backend operations across IO.
actor NativeLibraryBackend {
    private let helperURL: URL?
    private var process: Process?
    private var input: FileHandle?
    private var output: FileHandle?
    private var buffer = Data()
    private var serial = 0
    nonisolated private let cancellation = BackendCancellation()
    init(helperURL: URL? = nil) { self.helperURL = helperURL }
    nonisolated func cancel() { cancellation.interrupt() }

    func recycle(_ context: LibraryRecycleContext, params: Data) throws -> URL? {
        // Recheck the tree while the native coordination lease is held, then
        // transfer it without allowing another actor request in between.
        try LibraryRecycler.recycle(context, validate: {
            _ = try request("validate_recycle", params: params)
        })
    }

    func request(_ method: String, params: Data = Data("{}".utf8), progress: @Sendable (Int, Int, String) -> Void = { _, _, _ in }) throws -> Data {
        if process?.isRunning != true { try start() }
        serial += 1
        let parameters = try JSONSerialization.jsonObject(with: params)
        var line = try JSONSerialization.data(withJSONObject: ["id": serial, "method": method, "params": parameters])
        line.append(10)
        guard let input else { throw NativeBackendError(message: "本机库服务未启动") }
        try input.write(contentsOf: line)
        while true {
            let packet = try readPacket()
            guard packet["id"] as? Int == serial else { throw NativeBackendError(message: "后台响应不属于当前请求；未自动重试操作") }
            if packet["type"] as? String == "progress" {
                progress(packet["done"] as? Int ?? 0, packet["total"] as? Int ?? 0, packet["message"] as? String ?? "")
                continue
            }
            guard packet["ok"] as? Bool == true else { throw NativeBackendError(message: packet["error"] as? String ?? "本机库操作失败") }
            return try JSONSerialization.data(withJSONObject: packet["value"] ?? NSNull(), options: .fragmentsAllowed)
        }
    }
    func close() {
        if process?.isRunning == true { _ = try? request("close") }
        stop()
    }
    private func start() throws {
        stop()
        guard let helper = helperURL ?? Bundle.main.url(forResource: "main", withExtension: "py", subdirectory: "Backend") else {
            throw NativeBackendError(message: "应用缺少本机照片库组件，请重新构建")
        }
        let bundled = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/Python/bin/python3")
        let child = Process()
        if FileManager.default.isExecutableFile(atPath: bundled.path) { child.executableURL = bundled }
        else if helperURL != nil { child.executableURL = URL(fileURLWithPath: "/usr/bin/python3") }
        else { throw NativeBackendError(message: "应用缺少内置运行组件，请重新构建") }
        child.arguments = ["-I", "-B", helper.path]
        let stdin = Pipe(), stdout = Pipe()
        child.standardInput = stdin; child.standardOutput = stdout; child.standardError = FileHandle.standardError
        try child.run()
        process = child; input = stdin.fileHandleForWriting; output = stdout.fileHandleForReading
        cancellation.install(child)
        let greeting = try readPacket()
        guard greeting["type"] as? String == "ready", greeting["protocol"] as? Int == 1,
              greeting["architecture"] as? String == "arm64" else {
            stop(); throw NativeBackendError(message: "后台协议或处理器架构不受支持")
        }
        cancellation.install(child, ready: true)
    }
    private func readPacket() throws -> [String: Any] {
        while true {
            if let end = buffer.firstIndex(of: 10) {
                let line = Data(buffer[..<end]); buffer.removeSubrange(...end)
                guard let packet = try JSONSerialization.jsonObject(with: line) as? [String: Any] else { throw NativeBackendError(message: "后台响应格式无效") }
                return packet
            }
            guard let output else { throw NativeBackendError(message: "后台输出已关闭") }
            // read(upToCount:) can wait to fill its buffer on a pipe; this protocol flushes short lines.
            let data = output.availableData
            guard !data.isEmpty else {
                cancellation.install(nil)
                throw NativeBackendError(message: "本机库服务已退出，当前操作状态需重新检查；未自动重试")
            }
            buffer.append(data)
            if buffer.count > 16 * 1024 * 1024 { throw NativeBackendError(message: "后台响应过大，请重新检查库状态") }
        }
    }
    private func stop() {
        cancellation.install(nil)
        try? input?.close(); try? output?.close()
        input = nil; output = nil; process = nil; buffer.removeAll()
        // EOF lets the helper finish/roll back its current group and release its lifetime lock.
    }
}

struct NativeLibraryState: Decodable, Sendable {
    let root: String?
    let writable: Bool
    let pending: [PendingOperation]
    struct PendingOperation: Decodable, Sendable { let id: String; let kind: String; let phase: String; let error: String? }
}
