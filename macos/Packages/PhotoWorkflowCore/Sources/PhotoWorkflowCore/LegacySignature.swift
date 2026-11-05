import Foundation
import CryptoKit
public enum LegacySignature {
    /// Only ASCII kind names and hex digests are valid persisted inputs.
    public static func hash(members: [(AssetKind, String)]) -> String {
        let sorted = members.sorted { ($0.0.rawValue, $0.1) < ($1.0.rawValue, $1.1) }
        let text = "[" + sorted.map { "('\($0.0.rawValue)', '\($0.1)')" }.joined(separator: ", ") + "]"
        return SHA256.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}
