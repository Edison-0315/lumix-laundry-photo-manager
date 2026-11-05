// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "PhotoWorkflowCore", platforms: [.macOS(.v14)], products: [.library(name: "PhotoWorkflowCore", targets: ["PhotoWorkflowCore"])], targets: [.target(name: "PhotoWorkflowCore"), .testTarget(name: "PhotoWorkflowCoreTests", dependencies: ["PhotoWorkflowCore"])])
