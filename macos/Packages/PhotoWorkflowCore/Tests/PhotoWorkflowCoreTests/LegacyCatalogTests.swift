import XCTest
import SQLite3
import CryptoKit
import Darwin
import ImageIO
import CoreGraphics
@testable import PhotoWorkflowCore

final class LegacyCatalogTests: XCTestCase {
    func testTrashAssetsAreReadableOnlyWithTheirMatchingTrashRecord() throws {
        try fixture { root, db in
            let relative = ".片集/回收站/p/a/A.JPG"
            let file = root.appendingPathComponent(relative)
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            let context = try XCTUnwrap(CGContext(data: nil, width: 2, height: 2, bitsPerComponent: 8, bytesPerRow: 8, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue))
            let destination = try XCTUnwrap(CGImageDestinationCreateWithURL(file as CFURL, "public.jpeg" as CFString, 1, nil))
            CGImageDestinationAddImage(destination, try XCTUnwrap(context.makeImage()), nil)
            XCTAssertTrue(CGImageDestinationFinalize(destination))
            try execute(db, """
            INSERT INTO activities VALUES('act','活动','活动');
            INSERT INTO people VALUES('person','act','待分类','待分类','unclassified',NULL);
            INSERT INTO photos(id,activity_id,person_id,stem,signature) VALUES('p','act','person','A','signature');
            INSERT INTO assets VALUES('a','p','jpeg','\(relative)','sha');
            """)
            XCTAssertNil(try LegacyCatalog.read(root: root).photos.first?.assets.first?.url)
            try execute(db, "INSERT INTO trashed_photos(photo_id,payload) VALUES('p','[]')")
            let photo = try XCTUnwrap(LegacyCatalog.read(root: root).photos.first)
            XCTAssertEqual(photo.assets.first?.url, file)
            XCTAssertEqual(photo.photo.files.count, 1)
            let source = try XCTUnwrap(SafeImageSource.open(try XCTUnwrap(photo.photo.files.first).url))
            XCTAssertNotNil(CGImageSourceCreateImageAtIndex(source, 0, nil))
            XCTAssertNil(CatalogPathResolver(root: root).resolve(".片集/catalog.sqlite3").url)
            try execute(db, "UPDATE assets SET path='.片集/回收站/p/other/A.JPG'")
            XCTAssertNil(try LegacyCatalog.read(root: root).photos.first?.assets.first?.url)
        }
    }
    private let schema = """
    CREATE TABLE activities(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,folder TEXT UNIQUE NOT NULL);
    CREATE TABLE people(id TEXT PRIMARY KEY,activity_id TEXT NOT NULL,name TEXT NOT NULL,folder TEXT NOT NULL,role TEXT,embedding TEXT,UNIQUE(activity_id,name));
    CREATE TABLE photos(id TEXT PRIMARY KEY,activity_id TEXT NOT NULL,person_id TEXT NOT NULL,stem TEXT NOT NULL,captured_at TEXT,edited INTEGER DEFAULT 0,manual_person INTEGER DEFAULT 0,opened_at TEXT,primary_export_id TEXT,signature TEXT NOT NULL,UNIQUE(activity_id,signature));
    CREATE TABLE assets(id TEXT PRIMARY KEY,photo_id TEXT NOT NULL,kind TEXT NOT NULL,path TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL);
    CREATE TABLE operations(id TEXT PRIMARY KEY,kind TEXT NOT NULL,phase TEXT NOT NULL,payload TEXT NOT NULL,error TEXT);
    CREATE TABLE detached_exports(id TEXT PRIMARY KEY,photo_id TEXT NOT NULL,path TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL);
    CREATE TABLE import_members(activity_id TEXT NOT NULL,kind TEXT NOT NULL,sha256 TEXT NOT NULL,photo_id TEXT NOT NULL,PRIMARY KEY(activity_id,kind,sha256,photo_id));
    CREATE TABLE trashed_photos(photo_id TEXT PRIMARY KEY,payload TEXT NOT NULL,deleted_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE purges(photo_id TEXT PRIMARY KEY,payload TEXT NOT NULL,error TEXT);
    CREATE TABLE deleted_activities(activity_id TEXT PRIMARY KEY);
    """
    private func fixture(_ body: (URL, OpaquePointer) throws -> Void) throws {
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent("Lumix-catalog-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: temp.appendingPathComponent(".片集"), withIntermediateDirectories: true)
        let buffer = realpath(temp.path, nil)!; defer { free(buffer) }
        let root = URL(fileURLWithPath: String(cString: buffer))
        defer { try? FileManager.default.removeItem(at: root) }
        var db: OpaquePointer?
        XCTAssertEqual(sqlite3_open(root.appendingPathComponent(".片集/catalog.sqlite3").path, &db), SQLITE_OK)
        let connection = try XCTUnwrap(db); defer { sqlite3_close(connection) }
        try execute(connection, schema)
        try body(root, connection)
    }
    private func execute(_ db: OpaquePointer, _ sql: String) throws {
        if sqlite3_exec(db, sql, nil, nil, nil) != SQLITE_OK { throw NSError(domain: String(cString: sqlite3_errmsg(db)), code: 1) }
    }
    private func hashes(_ root: URL) throws -> [String: Data] {
        let files = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey])!
        var result: [String: Data] = [:]
        for case let url as URL in files where try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true {
            result[url.path] = Data(SHA256.hash(data: try Data(contentsOf: url)))
        }
        return result
    }
    // Opening old metadata must preserve IDs, flags and all ten tables, without migration SQL.
    func testTenTablesAndReadOnlyWindowsRootMapping() throws {
        try fixture { root, db in
            try FileManager.default.createDirectory(at: root.appendingPathComponent("活动/人物"), withIntermediateDirectories: true)
            try Data("synthetic photo".utf8).write(to: root.appendingPathComponent("活动/人物/A.JPG"))
            try execute(db, #"""
            INSERT INTO activities VALUES('a','活动','活动');
            INSERT INTO people VALUES('p','a','人物','人物',NULL,'[0.1,0.2]');
            INSERT INTO photos VALUES('one','a','p','A','2026-11-04T00:15:00',1,1,NULL,'export-one','sig1');
            INSERT INTO photos VALUES('two','a','p','B',NULL,0,0,NULL,NULL,'sig2');
            INSERT INTO assets VALUES('asset-one','one','jpeg','D:\库\活动\人物\A.JPG','original-hash');
            INSERT INTO import_members VALUES('a','jpeg','original-hash','one');
            INSERT INTO trashed_photos(photo_id,payload) VALUES('two','{"original":"D:\\\\库\\\\B.JPG"}');
            INSERT INTO purges VALUES('two','{}','interrupted');
            INSERT INTO detached_exports VALUES('d','one','D:\库\活动\人物\missing.JPG','h');
            INSERT INTO operations VALUES('op','import','running','{"changes":[],"sql":[["DELETE FROM photos",[]]]}',NULL);
            """#)
            let before = try hashes(root)
            let catalog = try LegacyCatalog.read(root: root, oldRoot: "d:\\库")
            XCTAssertEqual(catalog.tables.count, 10)
            XCTAssertEqual(catalog.rows("import_members").first?.text("sha256"), "original-hash")
            XCTAssertEqual(catalog.rows("people").first?.text("embedding"), "[0.1,0.2]")
            let photo = try XCTUnwrap(catalog.photos.first { $0.id == "one" })
            XCTAssertEqual(photo.photo.capturedAt, "2026-11-04T00:15:00")
            XCTAssertTrue(photo.photo.edited); XCTAssertEqual(photo.photo.primaryExportID, "export-one")
            XCTAssertEqual(photo.assets.first?.url?.path, root.appendingPathComponent("活动/人物/A.JPG").path)
            XCTAssertNil(photo.assets.first?.problem)
            XCTAssertEqual(catalog.photos.first { $0.id == "two" }?.trashed, true)
            XCTAssertEqual(catalog.photos.first { $0.id == "two" }?.purging, true)
            XCTAssertTrue(catalog.issues.contains { $0.message.contains("未完成") })
            XCTAssertEqual(try hashes(root), before)
        }
    }
    // Reading only the main database or using immutable=1 loses uncheckpointed WAL rows.
    func testWALSnapshotDoesNotTouchOriginalSidecars() throws {
        try fixture { root, db in
            try execute(db, "PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0; INSERT INTO activities VALUES('wal','WAL活动','WAL活动');")
            let before = try hashes(root)
            let result = try LegacyCatalog.read(root: root)
            XCTAssertEqual(result.rows("activities").first?.text("id"), "wal")
            XCTAssertEqual(try hashes(root), before)
        }
    }
    // Out-of-root paths and symlinks must never become previewable assets.
    func testUnsafeAndUnmappedAssetsAreRetainedAsDiagnostics() throws {
        try fixture { root, db in
            try FileManager.default.createSymbolicLink(atPath: root.appendingPathComponent("link.JPG").path, withDestinationPath: "/etc/hosts")
            try execute(db, #"""
            INSERT INTO photos VALUES('one','a','p','A',NULL,0,0,NULL,NULL,'sig');
            INSERT INTO assets VALUES('outside','one','jpeg','D:\库2\A.JPG','h');
            INSERT INTO assets VALUES('traversal','one','raw','D:\库\..\A.RW2','h');
            INSERT INTO assets VALUES('link','one','jpeg','D:\库\link.JPG','h');
            INSERT INTO assets VALUES('relative','one','xmp','safe/A.xmp','h');
            INSERT INTO operations VALUES('bad','unknown','future','bad-json',NULL);
            """#)
            let result = try LegacyCatalog.read(root: root, oldRoot: "D:/库")
            let assets = try XCTUnwrap(result.photos.first?.assets)
            XCTAssertEqual(assets.count, 4)
            for id in ["outside", "traversal", "link"] {
                XCTAssertNil(assets.first { $0.id == id }?.url)
                XCTAssertNotNil(assets.first { $0.id == id }?.problem)
            }
            XCTAssertTrue(result.issues.contains { $0.message.contains("JSON") })
            XCTAssertEqual(result.rows("operations").first?.text("payload"), "bad-json")
        }
    }
    func testMissingSchemaIsRejectedWithoutCreatingTables() throws {
        try fixture { root, db in
            try execute(db, "DROP TABLE purges")
            let before = try hashes(root)
            XCTAssertThrowsError(try LegacyCatalog.read(root: root))
            XCTAssertEqual(try hashes(root), before)
        }
    }
    func testOriginalTrashPayloadArrayIsRecognizedAndPreserved() throws {
        try fixture { root, db in
            try execute(db, #"INSERT INTO trashed_photos(photo_id,payload) VALUES('trash','[{"table":"assets","id":"a","original":"D:/库/A.JPG"}]')"#)
            let catalog = try LegacyCatalog.read(root: root)
            XCTAssertFalse(catalog.issues.contains { $0.id.hasPrefix("json:trashed_photos:") })
            XCTAssertEqual(catalog.rows("trashed_photos").first?.text("payload"), #"[{"table":"assets","id":"a","original":"D:/库/A.JPG"}]"#)
        }
    }
    func testUNCMappingUsesWholeComponentsAndRequiresExplicitRoot() throws {
        try fixture { root, _ in
            try Data("test".utf8).write(to: root.appendingPathComponent("A.JPG"))
            let unc = CatalogPathResolver(root: root, oldRoot: "//Server/Share/库")
            XCTAssertEqual(unc.resolve("//server/share/库/A.JPG").url?.path, root.appendingPathComponent("A.JPG").path)
            XCTAssertNil(unc.resolve("//server/share/库2/A.JPG").url)
            XCTAssertNil(CatalogPathResolver(root: root).resolve("D:/库/A.JPG").url)
            XCTAssertNil(CatalogPathResolver(root: root, oldRoot: "D:").resolve("D:/A.JPG").url)
            XCTAssertNil(CatalogPathResolver(root: root, oldRoot: "//server").resolve("//server/share/A.JPG").url)
        }
    }
    func testRecoveryJournalIsRefusedAndPreserved() throws {
        try fixture { root, _ in
            try Data("unknown rollback journal".utf8).write(to: root.appendingPathComponent(".片集/catalog.sqlite3-journal"))
            let before = try hashes(root)
            XCTAssertThrowsError(try LegacyCatalog.read(root: root))
            XCTAssertEqual(try hashes(root), before)
        }
    }
}
