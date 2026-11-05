import Foundation
import SQLite3
let project = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let root = project.appendingPathComponent("build/fixtures/LegacyLibrary")
let dbURL = root.appendingPathComponent(".片集/catalog.sqlite3")
if FileManager.default.fileExists(atPath: dbURL.path) { exit(0) }
try FileManager.default.createDirectory(at: root.appendingPathComponent(".片集"), withIntermediateDirectories: true)
try FileManager.default.createDirectory(at: root.appendingPathComponent("活动/人物"), withIntermediateDirectories: true)
try FileManager.default.copyItem(at: project.appendingPathComponent("build/fixtures/UITestSource/JPEG/A.JPG"), to: root.appendingPathComponent("活动/人物/A.JPG"))
try FileManager.default.copyItem(at: project.appendingPathComponent("build/fixtures/UITestSource/Other/B.JPG"), to: root.appendingPathComponent("活动/人物/B.JPG"))
var db: OpaquePointer?
guard sqlite3_open(dbURL.path, &db) == SQLITE_OK, let db else { fatalError("Cannot create synthetic library") }
defer { sqlite3_close(db) }
let sql = #"""
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
INSERT INTO activities VALUES('activity','测试活动','活动');
INSERT INTO people VALUES('person','activity','人物','人物',NULL,'[0.1,0.2]');
INSERT INTO people VALUES('unclassified','activity','待分类','待分类','unclassified',NULL);
INSERT INTO photos VALUES('library-a','activity','person','库照片 A','2026-11-04T00:15:00',0,1,NULL,NULL,'sig-a');
INSERT INTO photos VALUES('library-b','activity','person','库照片 B','2026-11-04T10:30:00',1,1,NULL,'export-b','sig-b');
INSERT INTO photos VALUES('library-trash','activity','unclassified','回收站照片 C',NULL,0,0,NULL,NULL,'sig-c');
INSERT INTO assets VALUES('asset-a','library-a','jpeg','D:\照片库\活动\人物\A.JPG','synthetic-original-hash');
INSERT INTO assets VALUES('export-b','library-b','export','活动/人物/B.JPG','synthetic-export-hash');
INSERT INTO assets VALUES('asset-c','library-trash','jpeg','活动/人物/missing.JPG','synthetic-missing-hash');
INSERT INTO import_members VALUES('activity','jpeg','synthetic-original-hash','library-a');
INSERT INTO trashed_photos(photo_id,payload) VALUES('library-trash','[]');
INSERT INTO operations VALUES('historical-op','import','committed','{"changes":[],"sql":[]}',NULL);
"""#
guard sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK else { fatalError(String(cString: sqlite3_errmsg(db))) }
print("Created synthetic ten-table library: \(root.path)")
